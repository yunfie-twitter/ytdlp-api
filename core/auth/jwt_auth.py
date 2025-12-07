"""JWT Authentication and API Key Management"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from functools import lru_cache
import jwt
import secrets
import asyncio

from core.config.settings import settings
from core.exceptions import APIException, InternalServerError
from infrastructure.redis_manager import redis_manager

logger = logging.getLogger(__name__)

class JWTAuth:
    """JWT authentication and API key management"""
    
    def __init__(self):
        self.algorithm = settings.JWT_ALGORITHM
        self.secret_key = settings.SECRET_KEY
        self.expiration_days = settings.JWT_EXPIRATION_DAYS
        self.key_prefix = settings.REDIS_API_KEY_PREFIX
    
    @staticmethod
    def is_enabled() -> bool:
        """Check if JWT auth is enabled"""
        return settings.ENABLE_JWT_AUTH
    
    @staticmethod
    def can_issue_keys() -> bool:
        """Check if API key issuance is enabled"""
        return bool(settings.API_KEY_ISSUE_PASSWORD)
    
    def create_token(
        self,
        api_key_id: str,
        user_id: Optional[str] = None,
        additional_claims: Optional[dict] = None
    ) -> str:
        """Create JWT token from API key ID"""
        try:
            now = datetime.now(timezone.utc)
            expiration = now + timedelta(days=self.expiration_days)
            
            payload = {
                "api_key_id": api_key_id,
                "iat": int(now.timestamp()),
                "exp": int(expiration.timestamp()),
                "type": "api_key"
            }
            
            if user_id:
                payload["user_id"] = user_id
            
            if additional_claims:
                payload.update(additional_claims)
            
            token = jwt.encode(
                payload,
                self.secret_key,
                algorithm=self.algorithm
            )
            
            logger.info(f"JWT token created for API key: {api_key_id[:20]}...")
            return token
        except Exception as e:
            logger.error(f"Error creating JWT token: {e}", exc_info=True)
            raise InternalServerError(
                "Failed to create authentication token",
                details={"reason": str(e)}
            )
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Verify API key exists in Redis
            api_key_id = payload.get("api_key_id")
            if not api_key_id:
                logger.warning("Token missing api_key_id")
                raise ValueError("Invalid token structure")
            
            # Check if API key is revoked
            key_data = asyncio.run(redis_manager.get(f"{self.key_prefix}{api_key_id}"))
            if not key_data:
                logger.warning(f"API key not found or revoked: {api_key_id[:20]}...")
                raise ValueError("API key not found or revoked")
            
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise APIException(
                "Token has expired",
                status_code=401,
                error_code="TOKEN_EXPIRED"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise APIException(
                "Invalid authentication token",
                status_code=401,
                error_code="INVALID_TOKEN"
            )
    
    async def issue_api_key(
        self,
        password: str,
        user_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Tuple[str, str]:
        """Issue new API key after password verification"""
        
        # Verify JWT auth and key issuance are enabled
        if not self.is_enabled():
            raise APIException(
                "JWT authentication is disabled",
                status_code=403,
                error_code="JWT_DISABLED"
            )
        
        if not self.can_issue_keys():
            raise APIException(
                "API key issuance is disabled",
                status_code=403,
                error_code="API_KEY_ISSUANCE_DISABLED"
            )
        
        # Verify password
        if password != settings.API_KEY_ISSUE_PASSWORD:
            logger.warning(f"Failed API key issuance attempt with wrong password")
            raise APIException(
                "Invalid password",
                status_code=401,
                error_code="INVALID_PASSWORD"
            )
        
        try:
            # Generate unique API key ID
            api_key_id = secrets.token_urlsafe(32)
            
            # Create JWT token
            token = self.create_token(
                api_key_id=api_key_id,
                user_id=user_id,
                additional_claims={
                    "description": description or "API Key"
                }
            )
            
            # Store API key metadata in Redis
            key_data = {
                "api_key_id": api_key_id,
                "token": token,
                "user_id": user_id or "anonymous",
                "description": description or "API Key",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_used": None,
                "active": True
            }
            
            # Store with TTL (expiration_days + 1 day buffer)
            ttl_seconds = (self.expiration_days + 1) * 86400
            await redis_manager.set(
                f"{self.key_prefix}{api_key_id}",
                key_data,
                ex=ttl_seconds
            )
            
            logger.info(
                f"API key issued: {api_key_id[:20]}... "
                f"user={user_id or 'anonymous'} "
                f"description={description}"
            )
            
            return api_key_id, token
        except Exception as e:
            logger.error(f"Error issuing API key: {e}", exc_info=True)
            raise InternalServerError(
                "Failed to issue API key",
                details={"reason": str(e)}
            )
    
    async def revoke_api_key(self, api_key_id: str) -> bool:
        """Revoke an API key"""
        try:
            key_path = f"{self.key_prefix}{api_key_id}"
            key_data = await redis_manager.get(key_path)
            
            if not key_data:
                logger.warning(f"API key not found for revocation: {api_key_id[:20]}...")
                return False
            
            # Mark as revoked by deleting from Redis
            await redis_manager.delete(key_path)
            
            logger.info(f"API key revoked: {api_key_id[:20]}...")
            return True
        except Exception as e:
            logger.error(f"Error revoking API key: {e}", exc_info=True)
            raise InternalServerError(
                "Failed to revoke API key",
                details={"reason": str(e)}
            )
    
    async def list_api_keys(self, user_id: Optional[str] = None) -> list:
        """List all active API keys (optionally filtered by user)"""
        try:
            # Get all keys matching prefix
            keys = await redis_manager.get_keys(f"{self.key_prefix}*")
            
            api_keys = []
            for key in keys:
                key_data = await redis_manager.get(key)
                if key_data:
                    if user_id is None or key_data.get("user_id") == user_id:
                        # Don't expose the token
                        key_data_safe = key_data.copy()
                        key_data_safe.pop("token", None)
                        api_keys.append(key_data_safe)
            
            logger.info(f"Listed {len(api_keys)} API keys")
            return api_keys
        except Exception as e:
            logger.error(f"Error listing API keys: {e}", exc_info=True)
            raise InternalServerError(
                "Failed to list API keys",
                details={"reason": str(e)}
            )
    
    async def update_api_key(
        self,
        api_key_id: str,
        description: Optional[str] = None,
        active: Optional[bool] = None
    ) -> bool:
        """Update API key metadata"""
        try:
            key_path = f"{self.key_prefix}{api_key_id}"
            key_data = await redis_manager.get(key_path)
            
            if not key_data:
                logger.warning(f"API key not found for update: {api_key_id[:20]}...")
                return False
            
            if description is not None:
                key_data["description"] = description
            
            if active is not None:
                key_data["active"] = active
            
            key_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Update in Redis
            ttl_seconds = (self.expiration_days + 1) * 86400
            await redis_manager.set(key_path, key_data, ex=ttl_seconds)
            
            logger.info(f"API key updated: {api_key_id[:20]}...")
            return True
        except Exception as e:
            logger.error(f"Error updating API key: {e}", exc_info=True)
            raise InternalServerError(
                "Failed to update API key",
                details={"reason": str(e)}
            )
    
    async def record_api_key_usage(self, api_key_id: str) -> bool:
        """Record API key last usage time"""
        try:
            key_path = f"{self.key_prefix}{api_key_id}"
            key_data = await redis_manager.get(key_path)
            
            if not key_data:
                return False
            
            key_data["last_used"] = datetime.now(timezone.utc).isoformat()
            
            # Update in Redis
            ttl_seconds = (self.expiration_days + 1) * 86400
            await redis_manager.set(key_path, key_data, ex=ttl_seconds)
            
            return True
        except Exception as e:
            logger.error(f"Error recording API key usage: {e}", exc_info=True)
            return False

# Global instance
jwt_auth = JWTAuth()
