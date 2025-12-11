"""Authentication and API key management endpoints"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from core import jwt_auth, verify_api_key
from core.exceptions import APIException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])

class IssueKeyRequest(BaseModel):
    """Request to issue new API key"""
    password: str
    user_id: Optional[str] = None
    description: Optional[str] = None

class IssueKeyResponse(BaseModel):
    """Response containing new API key"""
    api_key_id: str
    token: str
    user_id: Optional[str]
    description: Optional[str]
    message: str

class RevokeKeyRequest(BaseModel):
    """Request to revoke API key"""
    api_key_id: str

class UpdateKeyRequest(BaseModel):
    """Request to update API key"""
    description: Optional[str] = None
    active: Optional[bool] = None

class APIKeyInfo(BaseModel):
    """API key information (without token)"""
    api_key_id: str
    user_id: Optional[str]
    description: Optional[str]
    created_at: str
    last_used: Optional[str]
    active: bool

@router.post("/issue-key", response_model=IssueKeyResponse)
async def issue_api_key(request: IssueKeyRequest):
    """Issue new API key after password verification"""
    
    if not jwt_auth.is_enabled():
        raise HTTPException(
            status_code=403,
            detail="JWT authentication is disabled"
        )
    
    if not jwt_auth.can_issue_keys():
        raise HTTPException(
            status_code=403,
            detail="API key issuance is disabled. Set API_KEY_ISSUE_PASSWORD in environment."
        )
    
    try:
        api_key_id, token = await jwt_auth.issue_api_key(
            password=request.password,
            user_id=request.user_id,
            description=request.description
        )
        
        return IssueKeyResponse(
            api_key_id=api_key_id,
            token=token,
            user_id=request.user_id,
            description=request.description,
            message="API key issued successfully. Use token in Authorization header: Bearer <token>"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Error issuing API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to issue API key"
        )

@router.post("/revoke-key")
async def revoke_api_key(
    request: RevokeKeyRequest,
    payload: dict = Depends(verify_api_key)
):
    """Revoke an API key"""
    
    if not jwt_auth.is_enabled():
        raise HTTPException(
            status_code=403,
            detail="JWT authentication is disabled"
        )
    
    try:
        success = await jwt_auth.revoke_api_key(request.api_key_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="API key not found"
            )
        
        return {"message": f"API key {request.api_key_id[:20]}... revoked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke API key"
        )

@router.get("/keys", response_model=list[APIKeyInfo])
async def list_api_keys(
    user_id: Optional[str] = None,
    payload: dict = Depends(verify_api_key)
):
    """List all API keys (optionally filtered by user)"""
    
    if not jwt_auth.is_enabled():
        raise HTTPException(
            status_code=403,
            detail="JWT authentication is disabled"
        )
    
    try:
        keys = await jwt_auth.list_api_keys(user_id=user_id)
        return [APIKeyInfo(**key) for key in keys]
    except Exception as e:
        logger.error(f"Error listing API keys: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to list API keys"
        )

@router.patch("/keys/{api_key_id}")
async def update_api_key(
    api_key_id: str,
    request: UpdateKeyRequest,
    payload: dict = Depends(verify_api_key)
):
    """Update API key metadata"""
    
    if not jwt_auth.is_enabled():
        raise HTTPException(
            status_code=403,
            detail="JWT authentication is disabled"
        )
    
    try:
        success = await jwt_auth.update_api_key(
            api_key_id=api_key_id,
            description=request.description,
            active=request.active
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="API key not found"
            )
        
        return {"message": f"API key {api_key_id[:20]}... updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to update API key"
        )

@router.get("/status")
async def get_auth_status():
    """Get authentication system status"""
    return {
        "jwt_enabled": jwt_auth.is_enabled(),
        "api_key_issuance_enabled": jwt_auth.can_issue_keys(),
        "algorithm": jwt_auth.algorithm,
        "expiration_days": jwt_auth.expiration_days
    }
