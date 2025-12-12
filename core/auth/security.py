"""Security utilities and middleware"""
import logging
from typing import Optional
from fastapi import Depends, HTTPException, Header, Request

from core.config.settings import settings
from core.auth.jwt_auth import jwt_auth
from core.exceptions import RateLimitError, APIException
from infrastructure.redis_manager import redis_manager

logger = logging.getLogger(__name__)

# Global redis manager reference
_redis_manager = None

def set_redis_manager(manager):
    """Set the redis manager instance"""
    global _redis_manager
    _redis_manager = manager

def _get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    Handles X-Forwarded-For header for proxied requests.
    """
    # Check for X-Forwarded-For header (set by reverse proxy)
    if "X-Forwarded-For" in request.headers:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ips = request.headers["X-Forwarded-For"].split(",")
        return ips[0].strip()
    
    # Check for X-Real-IP header (set by some proxies)
    if "X-Real-IP" in request.headers:
        return request.headers["X-Real-IP"].strip()
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    # Default fallback
    return "0.0.0.0"

async def check_rate_limit(request: Request) -> str:
    """
    Check rate limit for client IP address.
    Automatically extracts IP from request.
    Returns the client IP address.
    """
    # Get client IP automatically
    client_ip = _get_client_ip(request)
    
    if _redis_manager is None:
        logger.warning("Redis manager not set for rate limiting")
        return client_ip
    
    try:
        limit = settings.RATE_LIMIT_PER_MINUTE
        key = f"rate_limit:{client_ip}"
        
        # Use increment_stat to increment the counter
        current = await _redis_manager.increment_stat(key)
        
        if current == 1:
            # Set expiration for the key (60 seconds)
            await _redis_manager.redis.expire(key, 60)
        
        if current > limit:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise RateLimitError(client_ip, limit, 60)
        
        return client_ip
    except RateLimitError:
        raise
    except Exception as e:
        logger.error(f"Error checking rate limit for {client_ip}: {e}")
        # Graceful degradation: allow request if Redis fails
        return client_ip

async def verify_api_key(
    authorization: Optional[str] = Header(None)
) -> Optional[dict]:
    """Verify API key from Authorization header"""
    
    # If JWT auth is disabled, skip verification
    if not jwt_auth.is_enabled():
        return None
    
    # Authorization header format: "Bearer <token>"
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = parts[1]
    
    try:
        payload = jwt_auth.verify_token(token)
        
        # Record API key usage
        api_key_id = payload.get("api_key_id")
        if api_key_id and _redis_manager:
            await jwt_auth.record_api_key_usage(api_key_id)
        
        return payload
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

async def get_optional_api_key(
    authorization: Optional[str] = Header(None)
) -> Optional[dict]:
    """Get API key if present, but don't require it"""
    if not authorization or not jwt_auth.is_enabled():
        return None
    
    try:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            payload = jwt_auth.verify_token(token)
            
            # Record API key usage
            api_key_id = payload.get("api_key_id")
            if api_key_id and _redis_manager:
                await jwt_auth.record_api_key_usage(api_key_id)
            
            return payload
    except Exception as e:
        logger.debug(f"Optional API key verification failed: {e}")
    
    return None

def is_feature_enabled(feature_flag: str) -> bool:
    """Check if a feature is enabled"""
    flag_name = f"ENABLE_FEATURE_{feature_flag.upper()}"
    return getattr(settings, flag_name, True)  # Default to True if not found
