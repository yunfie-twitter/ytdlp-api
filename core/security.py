"""Security features - rate limiting and authentication"""
import logging
from fastapi import Request, HTTPException
from typing import Optional

logger = logging.getLogger(__name__)

# This will be set by the app
_redis_manager = None

def set_redis_manager(redis_mgr):
    """Set the Redis manager instance"""
    global _redis_manager
    _redis_manager = redis_mgr

async def check_rate_limit(request: Request) -> str:
    """Check rate limit for IP address"""
    if _redis_manager is None:
        logger.warning("Redis manager not initialized, skipping rate limit check")
        return request.client.host if request.client else "unknown"
    
    ip = request.client.host if request.client else "unknown"
    
    try:
        allowed = await _redis_manager.check_rate_limit(ip)
        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        # Allow request if redis is down (graceful degradation)
    
    return ip
