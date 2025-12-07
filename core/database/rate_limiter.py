"""Advanced rate limiting system"""
import logging
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)

class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: int = 60, period: int = 60):
        self.rate = rate  # Requests per period
        self.period = period  # Time period in seconds
        self.requests: Dict[str, list] = defaultdict(list)
    
    async def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.period)
        
        # Remove old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]
        
        # Check if limit exceeded
        if len(self.requests[client_id]) >= self.rate:
            return False
        
        # Record this request
        self.requests[client_id].append(now)
        return True
    
    async def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.period)
        
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]
        
        return max(0, self.rate - len(self.requests[client_id]))
    
    async def get_reset_time(self, client_id: str) -> Optional[datetime]:
        """Get when rate limit resets"""
        if not self.requests[client_id]:
            return None
        
        oldest = min(self.requests[client_id])
        return oldest + timedelta(seconds=self.period)

# Global instance
rate_limiter = RateLimiter()
