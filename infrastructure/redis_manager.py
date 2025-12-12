"""Optimized Redis connection and operations manager"""
import logging
import json
from typing import Any, Optional, Dict, List
import asyncio
from datetime import timedelta
from redis import asyncio as aioredis

from core.config import settings
from core.exceptions import RedisError
from core.error_handling import async_retry, RetryConfig

logger = logging.getLogger(__name__)

class RedisManager:
    """Optimized Redis manager with connection pooling and error handling"""
    
    def __init__(self):
        self.redis = None
        self.connected = False
        self.connection_attempts = 0
        self.max_connection_attempts = 5
        self.retry_config = RetryConfig(
            max_attempts=3,
            backoff=0.5,
            backoff_multiplier=2.0,
            exceptions=(Exception,)
        )
    
    async def connect(self) -> bool:
        """Connect to Redis with retry"""
        if self.connected:
            return True
        
        try:
            self.redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={6: 1},  # TCP_KEEPIDLE
                health_check_interval=30
            )
            self.connected = True
            self.connection_attempts = 0
            logger.info(f"Connected to Redis: {settings.REDIS_URL}")
            return True
        except Exception as e:
            self.connection_attempts += 1
            logger.error(f"Failed to connect to Redis (attempt {self.connection_attempts}): {e}")
            raise RedisError(f"Redis connection failed: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.redis:
            try:
                await self.redis.close()
                self.connected = False
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
    
    async def ping(self) -> bool:
        """Ping Redis server"""
        if not self.connected:
            return False
        
        try:
            result = await asyncio.wait_for(self.redis.ping(), timeout=5)
            return result
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            self.connected = False
            return False
    
    @async_retry(RetryConfig(
        max_attempts=3,
        backoff=0.5,
        exceptions=(Exception,)
    ))
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis with auto JSON deserialization"""
        try:
            value = await self.redis.get(key)
            if value and (value.startswith('{') or value.startswith('[')):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            raise
    
    @async_retry(RetryConfig(
        max_attempts=3,
        backoff=0.5,
        exceptions=(Exception,)
    ))
    async def set(self, key: str, value: Any, ex: int = 3600) -> bool:
        """Set value in Redis with auto JSON serialization"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await self.redis.set(key, value, ex=ex)
            return True
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            raise
    
    @async_retry(RetryConfig(
        max_attempts=3,
        backoff=0.5,
        exceptions=(Exception,)
    ))
    async def delete(self, *keys: str) -> int:
        """Delete keys from Redis"""
        try:
            return await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            raise
    
    @async_retry(RetryConfig(
        max_attempts=3,
        backoff=0.5,
        exceptions=(Exception,)
    ))
    async def increment_stat(self, key: str) -> int:
        """Increment statistic counter"""
        try:
            return await self.redis.incr(key)
        except Exception as e:
            logger.error(f"Redis INCR error for key {key}: {e}")
            raise
    
    @async_retry(RetryConfig(
        max_attempts=3,
        backoff=0.5,
        exceptions=(Exception,)
    ))
    async def get_stat(self, key: str) -> int:
        """Get statistic value"""
        try:
            value = await self.redis.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Redis GET stat error for key {key}: {e}")
            return 0
    
    async def add_to_queue(self, task_id: str) -> bool:
        """Add task to queue"""
        try:
            await self.redis.lpush("pending_tasks", task_id)
            return True
        except Exception as e:
            logger.error(f"Failed to add task to queue: {e}")
            return False
    
    async def get_next_pending(self) -> Optional[str]:
        """Get next pending task"""
        try:
            task_id = await self.redis.rpop("pending_tasks")
            return task_id
        except Exception as e:
            logger.error(f"Failed to get pending task: {e}")
            return None
    
    async def can_start_download(self) -> bool:
        """Check if we can start a download"""
        try:
            active_count = await self.redis.scard("active_downloads")
            return active_count < settings.MAX_CONCURRENT_DOWNLOADS
        except Exception as e:
            logger.error(f"Failed to check download capacity: {e}")
            return False
    
    async def add_to_active(self, task_id: str) -> bool:
        """Add task to active downloads"""
        try:
            await self.redis.sadd("active_downloads", task_id)
            return True
        except Exception as e:
            logger.error(f"Failed to add task to active: {e}")
            return False
    
    async def remove_from_active(self, task_id: str) -> bool:
        """Remove task from active downloads"""
        try:
            await self.redis.srem("active_downloads", task_id)
            return True
        except Exception as e:
            logger.error(f"Failed to remove task from active: {e}")
            return False
    
    async def get_queue_size(self) -> int:
        """Get pending queue size"""
        try:
            return await self.redis.llen("pending_tasks")
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0
    
    async def get_active_count(self) -> int:
        """Get active downloads count"""
        try:
            return await self.redis.scard("active_downloads")
        except Exception as e:
            logger.error(f"Failed to get active count: {e}")
            return 0
    
    async def set_progress(self, task_id: str, progress_data: Dict) -> bool:
        """Set progress data"""
        try:
            key = f"progress:{task_id}"
            return await self.set(key, progress_data, ex=86400*7)
        except Exception as e:
            logger.error(f"Failed to set progress: {e}")
            return False

# Global instance
redis_manager = RedisManager()
