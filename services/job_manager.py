"""Optimized job management system with advanced scheduling and monitoring"""
import logging
import asyncio
from typing import Optional, Dict, List, Callable
from datetime import datetime, timezone
from enum import Enum
import uuid

from infrastructure.redis_manager import redis_manager
from core.config import settings
from core.error_handler import ErrorContext, retry, APIError

logger = logging.getLogger(__name__)

class JobPriority(int, Enum):
    """Job priority levels (higher = more important)"""
    LOWEST = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class JobStatus(str, Enum):
    """Job status states"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class Job:
    """Represents a single job"""
    
    def __init__(
        self,
        task_id: str,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        timeout: int = 3600
    ):
        self.job_id = str(uuid.uuid4())
        self.task_id = task_id
        self.priority = priority
        self.status = JobStatus.PENDING
        self.max_retries = max_retries
        self.retry_count = 0
        self.timeout = timeout
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.result: Optional[Dict] = None
    
    def to_dict(self) -> dict:
        """Convert job to dictionary"""
        return {
            "job_id": self.job_id,
            "task_id": self.task_id,
            "priority": self.priority.name,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "duration": (
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at and self.completed_at else None
            )
        }

class JobQueue:
    """Optimized priority queue for job management"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or settings.MAX_CONCURRENT_DOWNLOADS
        self.priority_queues: Dict[int, asyncio.Queue] = {
            priority.value: asyncio.Queue() for priority in JobPriority
        }
        self.active_jobs: Dict[str, Job] = {}
        self.completed_jobs: Dict[str, Job] = {}
        self.failed_jobs: Dict[str, Job] = {}
        self.job_metadata: Dict[str, Dict] = {}  # Store job metadata for monitoring
    
    async def enqueue(
        self,
        task_id: str,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        timeout: int = 3600
    ) -> Job:
        """Add job to queue"""
        with ErrorContext("enqueue_job", task_id=task_id):
            job = Job(
                task_id=task_id,
                priority=priority,
                max_retries=max_retries,
                timeout=timeout
            )
            
            # Store metadata
            self.job_metadata[job.job_id] = {
                "priority": priority.name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "enqueued_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Enqueue by priority
            queue = self.priority_queues[priority.value]
            await queue.put(job)
            
            logger.info(f"Job enqueued: {job.job_id} (task: {task_id}, priority: {priority.name})")
            await redis_manager.increment_stat(f"jobs:enqueued:{priority.name}")
            
            return job
    
    async def dequeue(self) -> Optional[Job]:
        """Get next job from highest priority queue"""
        # Check queues from highest to lowest priority
        for priority in sorted(self.priority_queues.keys(), reverse=True):
            queue = self.priority_queues[priority]
            if not queue.empty():
                try:
                    job = queue.get_nowait()
                    self.active_jobs[job.job_id] = job
                    job.status = JobStatus.RUNNING
                    job.started_at = datetime.now(timezone.utc)
                    logger.info(f"Job dequeued: {job.job_id} (priority: {JobPriority(priority).name})")
                    return job
                except asyncio.QueueEmpty:
                    continue
        
        return None
    
    async def mark_completed(self, job_id: str, result: Optional[Dict] = None) -> bool:
        """Mark job as completed"""
        if job_id not in self.active_jobs:
            logger.warning(f"Attempted to complete non-active job: {job_id}")
            return False
        
        job = self.active_jobs.pop(job_id)
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.result = result
        
        self.completed_jobs[job_id] = job
        
        # Update metadata
        if job_id in self.job_metadata:
            self.job_metadata[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            self.job_metadata[job_id]["status"] = "completed"
        
        await redis_manager.increment_stat(f"jobs:completed")
        
        logger.info(f"Job completed: {job_id} (duration: {(job.completed_at - job.started_at).total_seconds():.2f}s)")
        
        return True
    
    async def mark_failed(
        self,
        job_id: str,
        error: str,
        should_retry: bool = True
    ) -> bool:
        """Mark job as failed (with retry logic)"""
        if job_id not in self.active_jobs:
            logger.warning(f"Attempted to fail non-active job: {job_id}")
            return False
        
        job = self.active_jobs.pop(job_id)
        job.error = error
        job.completed_at = datetime.now(timezone.utc)
        
        # Check if we should retry
        if should_retry and job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = JobStatus.RETRYING
            
            # Re-enqueue with same priority
            queue = self.priority_queues[job.priority.value]
            await queue.put(job)
            
            logger.info(f"Job re-enqueued for retry: {job_id} (attempt {job.retry_count}/{job.max_retries})")
            await redis_manager.increment_stat(f"jobs:retried")
            
            # Remove from active, don't add to failed
            self.active_jobs[job_id] = job
        else:
            # Permanent failure
            job.status = JobStatus.FAILED
            self.failed_jobs[job_id] = job
            
            # Update metadata
            if job_id in self.job_metadata:
                self.job_metadata[job_id]["failed_at"] = datetime.now(timezone.utc).isoformat()
                self.job_metadata[job_id]["status"] = "failed"
                self.job_metadata[job_id]["error"] = error
            
            await redis_manager.increment_stat(f"jobs:failed")
            
            logger.error(f"Job failed permanently: {job_id} - {error}")
        
        return True
    
    async def mark_cancelled(self, job_id: str) -> bool:
        """Mark job as cancelled"""
        job = self.active_jobs.pop(job_id, None)
        if not job:
            logger.warning(f"Attempted to cancel non-active job: {job_id}")
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        
        # Update metadata
        if job_id in self.job_metadata:
            self.job_metadata[job_id]["cancelled_at"] = datetime.now(timezone.utc).isoformat()
            self.job_metadata[job_id]["status"] = "cancelled"
        
        await redis_manager.increment_stat(f"jobs:cancelled")
        
        logger.info(f"Job cancelled: {job_id}")
        
        return True
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return (
            self.active_jobs.get(job_id) or
            self.completed_jobs.get(job_id) or
            self.failed_jobs.get(job_id)
        )
    
    def get_active_count(self) -> int:
        """Get number of active jobs"""
        return len(self.active_jobs)
    
    def can_add_job(self) -> bool:
        """Check if we can add more jobs"""
        return len(self.active_jobs) < self.max_workers
    
    async def get_stats(self) -> dict:
        """Get queue statistics"""
        queued_count = sum(q.qsize() for q in self.priority_queues.values())
        
        return {
            "active": len(self.active_jobs),
            "queued": queued_count,
            "completed": len(self.completed_jobs),
            "failed": len(self.failed_jobs),
            "max_workers": self.max_workers,
            "capacity_used": len(self.active_jobs) / self.max_workers,
            "stats": {
                "enqueued": await redis_manager.get_stat("jobs:enqueued"),
                "completed": await redis_manager.get_stat("jobs:completed"),
                "failed": await redis_manager.get_stat("jobs:failed"),
                "retried": await redis_manager.get_stat("jobs:retried"),
                "cancelled": await redis_manager.get_stat("jobs:cancelled")
            }
        }
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed jobs"""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        
        removed_count = 0
        
        # Clean completed jobs
        to_remove = [
            job_id for job_id, job in self.completed_jobs.items()
            if job.completed_at.timestamp() < cutoff
        ]
        for job_id in to_remove:
            del self.completed_jobs[job_id]
            if job_id in self.job_metadata:
                del self.job_metadata[job_id]
            removed_count += 1
        
        # Clean failed jobs
        to_remove = [
            job_id for job_id, job in self.failed_jobs.items()
            if job.completed_at.timestamp() < cutoff
        ]
        for job_id in to_remove:
            del self.failed_jobs[job_id]
            if job_id in self.job_metadata:
                del self.job_metadata[job_id]
            removed_count += 1
        
        logger.info(f"Cleaned up {removed_count} old jobs")
        return removed_count

# Global instance
job_queue = JobQueue()
