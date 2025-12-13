"""Redis connection resilience with retry logic and fallback"""
import logging
import asyncio
from typing import Optional, Any, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RedisRetryPolicy:
    """Implements exponential backoff retry policy for Redis operations"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 0.5,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    async def execute_with_retry(
        self,
        operation: Callable,
        operation_name: str = "Redis operation",
        *args,
        **kwargs
    ) -> Optional[Any]:
        """Execute operation with exponential backoff retry
        
        Returns:
            Operation result or None if all retries failed
        """
        delay = self.initial_delay
        
        for attempt in range(self.max_retries + 1):
            try:
                result = operation(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                return result
            
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(
                        f"{operation_name} failed after {self.max_retries + 1} attempts: {e}"
                    )
                    return None
                
                logger.warning(
                    f"{operation_name} attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * self.backoff_factor, self.max_delay)
    
    async def execute_with_async_retry(
        self,
        operation: Callable,
        operation_name: str = "Redis operation",
        *args,
        **kwargs
    ) -> Optional[Any]:
        """Execute async operation with exponential backoff retry
        
        Returns:
            Operation result or None if all retries failed
        """
        delay = self.initial_delay
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await operation(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                return result
            
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(
                        f"{operation_name} failed after {self.max_retries + 1} attempts: {e}"
                    )
                    return None
                
                logger.warning(
                    f"{operation_name} attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * self.backoff_factor, self.max_delay)


class RedisFallbackCache:
    """In-memory fallback cache when Redis is unavailable"""
    
    def __init__(self, max_items: int = 1000, ttl_seconds: int = 3600):
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self.cache: dict = {}
        self.expiry: dict = {}
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in fallback cache"""
        try:
            if len(self.cache) >= self.max_items:
                # Remove oldest item
                oldest_key = min(self.expiry, key=self.expiry.get)
                del self.cache[oldest_key]
                del self.expiry[oldest_key]
            
            ttl = ttl or self.ttl_seconds
            expiry_time = datetime.utcnow() + timedelta(seconds=ttl)
            
            self.cache[key] = value
            self.expiry[key] = expiry_time
            return True
        except Exception as e:
            logger.error(f"Error setting fallback cache: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from fallback cache"""
        try:
            if key not in self.cache:
                return None
            
            # Check expiry
            if datetime.utcnow() > self.expiry.get(key, datetime.utcnow()):
                del self.cache[key]
                del self.expiry[key]
                return None
            
            return self.cache[key]
        except Exception as e:
            logger.error(f"Error getting fallback cache: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete value from fallback cache"""
        try:
            if key in self.cache:
                del self.cache[key]
                del self.expiry[key]
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting from fallback cache: {e}")
            return False
    
    def clear(self):
        """Clear fallback cache"""
        self.cache.clear()
        self.expiry.clear()
    
    def cleanup_expired(self):
        """Remove expired items from cache"""
        now = datetime.utcnow()
        expired_keys = [
            k for k, exp_time in self.expiry.items()
            if now > exp_time
        ]
        for key in expired_keys:
            del self.cache[key]
            del self.expiry[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache items")


# Global instances
redis_retry_policy = RedisRetryPolicy()
redis_fallback_cache = RedisFallbackCache()
