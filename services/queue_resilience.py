"""Resilient queue operations with automatic recovery and deadlock prevention"""
import logging
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import json

from infrastructure.redis_resilience import redis_retry_policy, redis_fallback_cache

logger = logging.getLogger(__name__)


class QueueHealthMonitor:
    """Monitors queue health and detects stuck/dead tasks"""
    
    def __init__(self):
        self.stuck_task_threshold_seconds = 3600  # 1 hour
        self.hung_task_threshold_seconds = 7200  # 2 hours
        self.last_check = None
        self.stuck_tasks: Dict[str, dict] = {}
        self.recovered_tasks: List[str] = []
    
    def mark_task_stuck(
        self,
        task_id: str,
        queue_key: str,
        reason: str
    ):
        """Mark a task as stuck for recovery"""
        self.stuck_tasks[task_id] = {
            "task_id": task_id,
            "queue_key": queue_key,
            "reason": reason,
            "detected_at": datetime.utcnow().isoformat(),
            "recovery_attempts": 0
        }
        logger.warning(
            f"Task {task_id} marked as stuck in {queue_key}: {reason}"
        )
    
    def mark_task_recovered(self, task_id: str):
        """Mark a stuck task as recovered"""
        if task_id in self.stuck_tasks:
            del self.stuck_tasks[task_id]
            self.recovered_tasks.append(task_id)
            logger.info(f"Task {task_id} recovered from stuck state")
    
    async def check_for_stuck_tasks(
        self,
        active_key: str,
        redis_conn
    ) -> List[str]:
        """Check for tasks that appear stuck in active set
        
        Returns:
            List of stuck task IDs
        """
        stuck_ids = []
        
        try:
            items = redis_conn.zrange(active_key, 0, -1, withscores=True)
            now = datetime.utcnow().timestamp()
            
            for item_bytes, enqueued_timestamp in items:
                item = json.loads(item_bytes)
                task_id = item.get("task_id")
                
                elapsed = now - enqueued_timestamp
                
                # Check if task has been active too long
                if elapsed > self.stuck_task_threshold_seconds:
                    stuck_ids.append(task_id)
                    self.mark_task_stuck(
                        task_id,
                        active_key,
                        f"Active for {elapsed:.0f}s"
                    )
            
            if stuck_ids:
                logger.warning(f"Found {len(stuck_ids)} potentially stuck tasks")
            
            return stuck_ids
        
        except Exception as e:
            logger.error(f"Error checking for stuck tasks: {e}")
            return []


class QueueDeadlockPrevention:
    """Prevent and detect queue deadlocks"""
    
    def __init__(self):
        self.lock_timeout_seconds = 60
        self.active_locks: Dict[str, datetime] = {}
    
    async def acquire_lock(
        self,
        resource_id: str,
        redis_conn,
        timeout: Optional[int] = None
    ) -> bool:
        """Acquire lock with timeout
        
        Returns:
            bool: True if lock acquired
        """
        timeout = timeout or self.lock_timeout_seconds
        
        try:
            lock_key = f"lock:{resource_id}"
            
            # Try to set lock (only if not exists)
            result = redis_conn.set(
                lock_key,
                datetime.utcnow().isoformat(),
                nx=True,
                ex=timeout
            )
            
            if result:
                self.active_locks[resource_id] = datetime.utcnow() + timedelta(seconds=timeout)
                logger.debug(f"Lock acquired for {resource_id}")
                return True
            else:
                logger.warning(f"Failed to acquire lock for {resource_id}")
                return False
        
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            return False
    
    async def release_lock(
        self,
        resource_id: str,
        redis_conn
    ) -> bool:
        """Release lock safely
        
        Returns:
            bool: True if lock released
        """
        try:
            lock_key = f"lock:{resource_id}"
            result = redis_conn.delete(lock_key)
            
            if resource_id in self.active_locks:
                del self.active_locks[resource_id]
            
            logger.debug(f"Lock released for {resource_id}")
            return result > 0
        
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
            return False
    
    def get_expired_locks(self) -> List[str]:
        """Get locks that have expired
        
        Returns:
            List of expired lock resource IDs
        """
        expired = []
        now = datetime.utcnow()
        
        for resource_id, expiry_time in list(self.active_locks.items()):
            if now > expiry_time:
                expired.append(resource_id)
                del self.active_locks[resource_id]
        
        return expired


class QueueRecoveryManager:
    """Manages queue recovery and task re-queueing"""
    
    async def recover_lost_tasks(
        self,
        queue_key: str,
        max_recovery_count: int = 100,
        redis_conn = None
    ) -> int:
        """Recover tasks that were lost due to failures
        
        Returns:
            Number of tasks recovered
        """
        if not redis_conn:
            return 0
        
        try:
            recovered_count = 0
            
            # Check for tasks that timed out
            items = redis_conn.zrange(queue_key, 0, max_recovery_count - 1, withscores=False)
            
            for item_bytes in items:
                try:
                    task_entry = json.loads(item_bytes)
                    task_id = task_entry.get("task_id")
                    
                    if task_entry.get("status") == "processing":
                        # Re-queue for retry
                        task_entry["status"] = "queued"
                        task_entry["recovery_attempt"] = task_entry.get("recovery_attempt", 0) + 1
                        
                        redis_conn.zadd(
                            queue_key,
                            {json.dumps(task_entry): 0},
                            xx=True
                        )
                        recovered_count += 1
                        logger.info(f"Recovered task {task_id}")
                
                except Exception as e:
                    logger.warning(f"Error recovering task: {e}")
            
            if recovered_count > 0:
                logger.info(f"Recovered {recovered_count} tasks from {queue_key}")
            
            return recovered_count
        
        except Exception as e:
            logger.error(f"Error in queue recovery: {e}")
            return 0
    
    async def requeue_failed_task(
        self,
        task_id: str,
        queue_key: str,
        max_retries: int = 3,
        redis_conn = None
    ) -> bool:
        """Re-queue a failed task with retry limit
        
        Returns:
            bool: True if re-queued
        """
        if not redis_conn:
            return False
        
        try:
            # Find the task
            items = redis_conn.zrange(queue_key, 0, -1, withscores=False)
            
            for item_bytes in items:
                task_entry = json.loads(item_bytes)
                if task_entry.get("task_id") == task_id:
                    retry_count = task_entry.get("retry_count", 0)
                    
                    if retry_count >= max_retries:
                        logger.warning(
                            f"Task {task_id} exceeded max retries ({max_retries})"
                        )
                        return False
                    
                    # Update retry count and re-queue
                    task_entry["retry_count"] = retry_count + 1
                    task_entry["status"] = "queued"
                    task_entry["last_retry"] = datetime.utcnow().isoformat()
                    
                    redis_conn.zadd(
                        queue_key,
                        {json.dumps(task_entry): -retry_count},  # Lower priority for retries
                        xx=True
                    )
                    
                    logger.info(f"Re-queued task {task_id} (attempt {retry_count + 1}/{max_retries})")
                    return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error re-queueing task: {e}")
            return False


# Global instances
queue_health_monitor = QueueHealthMonitor()
queue_deadlock_prevention = QueueDeadlockPrevention()
queue_recovery_manager = QueueRecoveryManager()
