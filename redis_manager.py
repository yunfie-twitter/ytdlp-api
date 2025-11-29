import redis.asyncio as redis
from typing import Optional
from config import settings
import json

class RedisManager:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        self.redis = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
    
    # Rate limiting
    async def check_rate_limit(self, ip: str) -> bool:
        """Check if IP has exceeded rate limit"""
        key = f"rate_limit:{ip}"
        count = await self.redis.get(key)
        
        if count is None:
            await self.redis.setex(key, 60, 1)
            return True
        
        if int(count) >= settings.RATE_LIMIT_PER_MINUTE:
            return False
        
        await self.redis.incr(key)
        return True
    
    # Queue management
    async def add_to_queue(self, task_id: str):
        """Add task to pending queue"""
        await self.redis.rpush("queue:pending", task_id)
    
    async def get_queue_position(self, task_id: str) -> int:
        """Get position in queue"""
        queue = await self.redis.lrange("queue:pending", 0, -1)
        try:
            return queue.index(task_id) + 1
        except ValueError:
            return 0
    
    async def get_active_downloads(self) -> list:
        """Get currently active download task IDs"""
        return await self.redis.smembers("queue:active")
    
    async def add_to_active(self, task_id: str):
        """Mark task as actively downloading"""
        await self.redis.sadd("queue:active", task_id)
        await self.redis.lrem("queue:pending", 0, task_id)
    
    async def remove_from_active(self, task_id: str):
        """Remove task from active downloads"""
        await self.redis.srem("queue:active", task_id)
    
    async def can_start_download(self) -> bool:
        """Check if we can start a new download"""
        active_count = await self.redis.scard("queue:active")
        return active_count < settings.MAX_CONCURRENT_DOWNLOADS
    
    async def get_next_pending(self) -> Optional[str]:
        """Get next pending task ID"""
        task_id = await self.redis.lpop("queue:pending")
        return task_id
    
    # Task progress
    async def set_progress(self, task_id: str, progress: dict):
        """Store task progress"""
        key = f"progress:{task_id}"
        await self.redis.setex(key, 7200, json.dumps(progress))
    
    async def get_progress(self, task_id: str) -> Optional[dict]:
        """Get task progress"""
        key = f"progress:{task_id}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None
    
    # WebSocket connections
    async def add_websocket(self, task_id: str, connection_id: str):
        """Register WebSocket connection for task"""
        key = f"ws:{task_id}"
        await self.redis.sadd(key, connection_id)
        await self.redis.expire(key, 7200)
    
    async def remove_websocket(self, task_id: str, connection_id: str):
        """Remove WebSocket connection"""
        key = f"ws:{task_id}"
        await self.redis.srem(key, connection_id)
    
    async def get_websockets(self, task_id: str) -> list:
        """Get all WebSocket connections for task"""
        key = f"ws:{task_id}"
        return list(await self.redis.smembers(key))

redis_manager = RedisManager()