"""Security utilities including rate limiting"""
import logging
from fastapi import HTTPException, Depends
from core.config import settings

logger = logging.getLogger(__name__)

# This will be injected by the service layer
_redis_manager = None

def set_redis_manager(manager):
    """Set the redis manager instance"""
    global _redis_manager
    _redis_manager = manager

async def check_rate_limit(ip: str = None) -> str:
    """Check rate limit for IP address"""
    if ip is None:
        ip = "unknown"
    
    if _redis_manager is None:
        return ip
    
    try:
        allowed = await _redis_manager.check_rate_limit(ip)
        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Maximum 3 requests per minute."
            )
        return ip
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        # Fail open - allow request if rate limiter fails
        return ip
