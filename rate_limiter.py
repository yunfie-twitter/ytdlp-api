from fastapi import Request, HTTPException
from redis_manager import redis_manager

async def check_rate_limit(request: Request):
    """Rate limiting middleware"""
    # Get client IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host
    
    # Check rate limit
    allowed = await redis_manager.check_rate_limit(ip)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    
    return ip