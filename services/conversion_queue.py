"""Queue management system for media conversion tasks"""
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from infrastructure.redis_manager import redis_manager

logger = logging.getLogger(__name__)


class ConversionQueueManager:
    """Manages the conversion task queue with priority support"""
    
    QUEUE_KEY = "conversion:queue"
    ACTIVE_KEY = "conversion:active"
    STATS_KEY = "conversion:stats"
    
    def __init__(self):
        self.redis = redis_manager.redis_conn
    
    async def enqueue(
        self,
        task_id: str,
        priority: int = 0,
        max_retries: int = 3,
        timeout: int = 14400
    ) -> bool:
        """Add a conversion task to the queue
        
        Args:
            task_id: ID of the conversion task
            priority: Priority level (higher = more important)
            max_retries: Maximum retry attempts
            timeout: Task timeout in seconds
        """
        try:
            queue_entry = {
                "task_id": task_id,
                "priority": priority,
                "max_retries": max_retries,
                "timeout": timeout,
                "enqueued_at": datetime.utcnow().isoformat(),
                "retry_count": 0,
                "status": "queued"
            }
            
            # Use sorted set with priority as score (higher score = higher priority)
            score = -priority  # Negative so higher priority comes first in ascending order
            self.redis.zadd(
                self.QUEUE_KEY,
                {json.dumps(queue_entry): score},
                nx=True  # Only add if not exists
            )
            
            logger.info(f"Task enqueued: {task_id} (priority: {priority})")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue task {task_id}: {e}")
            return False
    
    async def dequeue(self) -> Optional[Dict]:
        """Get the next highest priority task from queue
        
        Returns:
            Task entry dict or None if queue is empty
        """
        try:
            # Get the first item (lowest score = highest priority)
            items = self.redis.zrange(self.QUEUE_KEY, 0, 0, withscores=False)
            
            if not items:
                return None
            
            task_entry = json.loads(items[0])
            
            # Move to active set
            self.redis.zadd(
                self.ACTIVE_KEY,
                {items[0]: 0},
                xx=False
            )
            
            # Remove from queue
            self.redis.zrem(self.QUEUE_KEY, items[0])
            
            logger.info(f"Task dequeued: {task_entry['task_id']}")
            return task_entry
        except Exception as e:
            logger.error(f"Failed to dequeue task: {e}")
            return None
    
    async def mark_active(self, task_id: str) -> bool:
        """Mark a task as currently being processed"""
        try:
            # Find the task in queue
            items = self.redis.zrange(self.QUEUE_KEY, 0, -1, withscores=False)
            
            for item in items:
                task_entry = json.loads(item)
                if task_entry["task_id"] == task_id:
                    task_entry["status"] = "active"
                    task_entry["started_at"] = datetime.utcnow().isoformat()
                    
                    # Move to active
                    self.redis.zadd(self.ACTIVE_KEY, {item: 0}, xx=False)
                    
                    # Remove from queue
                    self.redis.zrem(self.QUEUE_KEY, item)
                    
                    logger.info(f"Task marked active: {task_id}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to mark task active: {e}")
            return False
    
    async def mark_completed(self, task_id: str, result: Optional[Dict] = None) -> bool:
        """Mark a task as completed"""
        try:
            # Find and remove from active
            items = self.redis.zrange(self.ACTIVE_KEY, 0, -1, withscores=False)
            
            for item in items:
                task_entry = json.loads(item)
                if task_entry["task_id"] == task_id:
                    task_entry["status"] = "completed"
                    task_entry["completed_at"] = datetime.utcnow().isoformat()
                    if result:
                        task_entry["result"] = result
                    
                    # Store in completed set (with 24h TTL)
                    self.redis.zadd(
                        "conversion:completed",
                        {json.dumps(task_entry): 0},
                        xx=False
                    )
                    self.redis.expire("conversion:completed", 86400)  # 24 hours
                    
                    # Remove from active
                    self.redis.zrem(self.ACTIVE_KEY, item)
                    
                    # Update stats
                    self.redis.hincrby(self.STATS_KEY, "completed", 1)
                    
                    logger.info(f"Task completed: {task_id}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to mark task completed: {e}")
            return False
    
    async def mark_failed(
        self,
        task_id: str,
        error_message: str,
        should_retry: bool = True
    ) -> bool:
        """Mark a task as failed
        
        Args:
            task_id: Task ID
            error_message: Error description
            should_retry: Whether to retry this task
        """
        try:
            # Find task
            items = self.redis.zrange(self.ACTIVE_KEY, 0, -1, withscores=False)
            if not items:
                items = self.redis.zrange(self.QUEUE_KEY, 0, -1, withscores=False)
            
            for item in items:
                task_entry = json.loads(item)
                if task_entry["task_id"] == task_id:
                    task_entry["status"] = "failed"
                    task_entry["error_message"] = error_message
                    task_entry["failed_at"] = datetime.utcnow().isoformat()
                    
                    retry_count = task_entry.get("retry_count", 0)
                    max_retries = task_entry.get("max_retries", 3)
                    
                    # Check if should retry
                    if should_retry and retry_count < max_retries:
                        task_entry["retry_count"] = retry_count + 1
                        task_entry["status"] = "queued"
                        
                        # Put back in queue
                        priority = task_entry.get("priority", 0) - (retry_count * 10)  # Lower priority for retries
                        score = -priority
                        self.redis.zadd(
                            self.QUEUE_KEY,
                            {json.dumps(task_entry): score},
                            xx=False
                        )
                        
                        # Remove from current location
                        self.redis.zrem(self.ACTIVE_KEY, item)
                        self.redis.zrem(self.QUEUE_KEY, item)
                        
                        # Update stats
                        self.redis.hincrby(self.STATS_KEY, "retried", 1)
                        
                        logger.warning(
                            f"Task failed but will retry: {task_id} (attempt {retry_count + 1}/{max_retries})"
                        )
                    else:
                        # Move to failed set
                        self.redis.zadd(
                            "conversion:failed",
                            {json.dumps(task_entry): 0},
                            xx=False
                        )
                        self.redis.expire("conversion:failed", 604800)  # 7 days
                        
                        # Remove from current location
                        self.redis.zrem(self.ACTIVE_KEY, item)
                        self.redis.zrem(self.QUEUE_KEY, item)
                        
                        # Update stats
                        self.redis.hincrby(self.STATS_KEY, "failed", 1)
                        
                        logger.error(f"Task failed (no more retries): {task_id}")
                    
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to mark task failed: {e}")
            return False
    
    async def mark_cancelled(self, task_id: str) -> bool:
        """Mark a task as cancelled"""
        try:
            items = self.redis.zrange(self.ACTIVE_KEY, 0, -1, withscores=False)
            if not items:
                items = self.redis.zrange(self.QUEUE_KEY, 0, -1, withscores=False)
            
            for item in items:
                task_entry = json.loads(item)
                if task_entry["task_id"] == task_id:
                    task_entry["status"] = "cancelled"
                    task_entry["cancelled_at"] = datetime.utcnow().isoformat()
                    
                    # Store in cancelled set
                    self.redis.zadd(
                        "conversion:cancelled",
                        {json.dumps(task_entry): 0},
                        xx=False
                    )
                    self.redis.expire("conversion:cancelled", 86400)  # 24 hours
                    
                    # Remove from current location
                    self.redis.zrem(self.ACTIVE_KEY, item)
                    self.redis.zrem(self.QUEUE_KEY, item)
                    
                    # Update stats
                    self.redis.hincrby(self.STATS_KEY, "cancelled", 1)
                    
                    logger.info(f"Task cancelled: {task_id}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to mark task cancelled: {e}")
            return False
    
    async def get_queue_size(self) -> int:
        """Get number of pending tasks in queue"""
        try:
            return self.redis.zcard(self.QUEUE_KEY)
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0
    
    async def get_active_count(self) -> int:
        """Get number of currently processing tasks"""
        try:
            return self.redis.zcard(self.ACTIVE_KEY)
        except Exception as e:
            logger.error(f"Failed to get active count: {e}")
            return 0
    
    async def get_stats(self) -> Dict:
        """Get conversion queue statistics"""
        try:
            stats = self.redis.hgetall(self.STATS_KEY)
            return {
                "queued": await self.get_queue_size(),
                "active": await self.get_active_count(),
                "completed": int(stats.get(b"completed", 0)),
                "failed": int(stats.get(b"failed", 0)),
                "cancelled": int(stats.get(b"cancelled", 0)),
                "retried": int(stats.get(b"retried", 0))
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed/failed/cancelled jobs
        
        Returns:
            Number of jobs removed
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            removed = 0
            
            for key in ["conversion:completed", "conversion:failed", "conversion:cancelled"]:
                items = self.redis.zrange(key, 0, -1, withscores=False)
                
                for item in items:
                    task_entry = json.loads(item)
                    timestamp_key = (
                        "completed_at" if "completed_at" in task_entry else
                        "failed_at" if "failed_at" in task_entry else
                        "cancelled_at"
                    )
                    
                    if timestamp_key in task_entry:
                        task_time = datetime.fromisoformat(task_entry[timestamp_key])
                        if task_time < cutoff_time:
                            self.redis.zrem(key, item)
                            removed += 1
            
            if removed > 0:
                logger.info(f"Cleaned up {removed} old conversion jobs")
            
            return removed
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0


conversion_queue = ConversionQueueManager()
