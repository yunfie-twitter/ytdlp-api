"""Logging middleware for request/response tracking"""
import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses with performance metrics"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Start timer
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "client": request.client.host if request.client else "unknown",
                "method": request.method,
                "path": request.url.path
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {request.method} {request.url.path} - {response.status_code} ({duration*1000:.2f}ms)",
            extra={
                "status_code": response.status_code,
                "duration_ms": duration * 1000,
                "path": request.url.path
            }
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(duration)
        
        return response
