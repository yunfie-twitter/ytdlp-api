"""Redis connection management and utilities"""
import redis.asyncio as redis
import logging
from typing import Optional
from core.config import settings
import json

logger = logging.getLogger(__name__)

class RedisManager:
    """Manages Redis connections and operations"""
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            # Test connection
            await self.redis.ping()
            logger.info("✅ Redis connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            try:
                await self.redis.close()
                logger.info("Redis disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting from Redis: {e}")
    
    async def ping(self) -> bool:
        """Health check for Redis connection"""
        try:
            if self.redis is None:
                return False
            result = await self.redis.ping()
            return result is True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    # Rate limiting
    async def check_rate_limit(self, ip: str) -> bool:
        """Check if IP has exceeded rate limit"""
        try:
            key = f"rate_limit:{ip}"
            count = await self.redis.get(key)
            
            if count is None:
                await self.redis.setex(key, 60, 1)
                return True
            
            if int(count) >= settings.RATE_LIMIT_PER_MINUTE:
                logger.warning(f"Rate limit exceeded for IP: {ip}")
                return False
            
            await self.redis.incr(key)
            return True
        except Exception as e:
            logger.error(f"Error checking rate limit for {ip}: {e}")
            return False
    
    # Queue management
    async def add_to_queue(self, task_id: str):
        """Add task to pending queue"""
        try:
            await self.redis.rpush("queue:pending", task_id)
            logger.info(f"Task added to queue: {task_id}")
        except Exception as e:
            logger.error(f"Error adding task to queue: {e}")
            raise
    
    async def get_queue_position(self, task_id: str) -> int:
        """Get position in queue"""
        try:
            queue = await self.redis.lrange("queue:pending", 0, -1)
            try:
                return queue.index(task_id) + 1
            except ValueError:
                return 0
        except Exception as e:
            logger.error(f"Error getting queue position for {task_id}: {e}")
            return 0
    
    async def get_active_downloads(self) -> list:
        """Get currently active download task IDs"""
        try:
            return list(await self.redis.smembers("queue:active"))
        except Exception as e:
            logger.error(f"Error getting active downloads: {e}")
            return []
    
    async def add_to_active(self, task_id: str):
        """Mark task as actively downloading"""
        try:
            await self.redis.sadd("queue:active", task_id)
            await self.redis.lrem("queue:pending", 0, task_id)
            logger.info(f"Task marked as active: {task_id}")
        except Exception as e:
            logger.error(f"Error marking task as active: {e}")
            raise
    
    async def remove_from_active(self, task_id: str):
        """Remove task from active downloads"""
        try:
            await self.redis.srem("queue:active", task_id)
            logger.info(f"Task removed from active: {task_id}")
        except Exception as e:
            logger.error(f"Error removing task from active: {e}")
    
    async def can_start_download(self) -> bool:
        """Check if we can start a new download"""
        try:
            active_count = await self.redis.scard("queue:active")
            can_start = active_count < settings.MAX_CONCURRENT_DOWNLOADS
            if not can_start:
                logger.info(f"Max concurrent downloads reached ({active_count}/{settings.MAX_CONCURRENT_DOWNLOADS})")
            return can_start
        except Exception as e:
            logger.error(f"Error checking if download can start: {e}")
            return False
    
    async def get_next_pending(self) -> Optional[str]:
        """Get next pending task ID"""
        try:
            task_id = await self.redis.lpop("queue:pending")
            if task_id:
                logger.info(f"Next pending task: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"Error getting next pending task: {e}")
            return None
    
    # Task progress
    async def set_progress(self, task_id: str, progress: dict):
        """Store task progress"""
        try:
            key = f"progress:{task_id}"
            await self.redis.setex(key, 7200, json.dumps(progress))
        except Exception as e:
            logger.error(f"Error setting progress for {task_id}: {e}")
    
    async def get_progress(self, task_id: str) -> Optional[dict]:
        """Get task progress"""
        try:
            key = f"progress:{task_id}"
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except json.JSONDecodeError:
            logger.error(f"Invalid progress data for {task_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting progress for {task_id}: {e}")
            return None
    
    # WebSocket connections
    async def add_websocket(self, task_id: str, connection_id: str):
        """Register WebSocket connection for task"""
        try:
            key = f"ws:{task_id}"
            await self.redis.sadd(key, connection_id)
            await self.redis.expire(key, 7200)
            logger.info(f"WebSocket connection added for task: {task_id}")
        except Exception as e:
            logger.error(f"Error adding WebSocket connection: {e}")
    
    async def remove_websocket(self, task_id: str, connection_id: str):
        """Remove WebSocket connection"""
        try:
            key = f"ws:{task_id}"
            await self.redis.srem(key, connection_id)
        except Exception as e:
            logger.error(f"Error removing WebSocket connection: {e}")
    
    async def get_websockets(self, task_id: str) -> list:
        """Get all WebSocket connections for task"""
        try:
            key = f"ws:{task_id}"
            return list(await self.redis.smembers(key))
        except Exception as e:
            logger.error(f"Error getting WebSocket connections: {e}")
            return []

redis_manager = RedisManager()
