"""Optimized queue worker with advanced job management and monitoring"""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import and_

from core.error_handling import ErrorContext
from core.config import settings
from infrastructure.redis_manager import redis_manager
from infrastructure.progress_tracker import progress_tracker
from services.download_service import download_service
from services.job_manager import job_queue, JobPriority
from infrastructure.database import get_db, DownloadTask

logger = logging.getLogger(__name__)

class OptimizedQueueWorker:
    """Manages download queue with priority scheduling and automatic recovery"""
    
    def __init__(self):
        self.running = False
        self.queue_task = None
        self.cleanup_task = None
        self.health_check_task = None
        self.error_count = 0
        self.max_errors = 10
        self.last_error: str = None
        self.worker_stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "tasks_succeeded": 0,
            "total_runtime": 0.0,
            "uptime_start": datetime.utcnow()
        }
    
    async def start(self):
        """Start all queue worker components"""
        logger.info("🚀 Starting optimized queue worker")
        self.running = True
        self.worker_stats["uptime_start"] = datetime.utcnow()
        
        try:
            await asyncio.gather(
                self.process_queue(),
                self.cleanup_old_tasks(),
                self.health_check_loop(),
                self.job_queue_monitor(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"💥 Fatal error in queue worker: {e}", exc_info=True)
            self.running = False
    
    async def stop(self):
        """Stop all queue worker components gracefully"""
        logger.info("🛑 Stopping queue worker")
        self.running = False
        
        tasks = [self.queue_task, self.cleanup_task, self.health_check_task]
        for task in tasks:
            if task:
                try:
                    await asyncio.wait_for(task, timeout=5)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    logger.warning(f"Task did not stop gracefully: {task}")
        
        logger.info(f"📊 Final stats - Processed: {self.worker_stats['tasks_processed']}, "
                   f"Succeeded: {self.worker_stats['tasks_succeeded']}, "
                   f"Failed: {self.worker_stats['tasks_failed']}")
    
    async def process_queue(self):
        """Process pending downloads with priority scheduling"""
        logger.info("📋 Queue processor started")
        
        while self.running:
            try:
                # Check if we can start more downloads
                can_start = await redis_manager.can_start_download()
                
                if can_start:
                    # Get next job from priority queue
                    job = await job_queue.dequeue()
                    
                    if job:
                        with ErrorContext("process_job", job_id=job.job_id, task_id=job.task_id):
                            db = next(get_db())
                            try:
                                task = db.query(DownloadTask).filter(DownloadTask.id == job.task_id).first()
                                if task:
                                    # Initialize progress tracking
                                    await progress_tracker.initialize_task(
                                        job.task_id,
                                        task.url,
                                        task.title
                                    )
                                    
                                    # Start download
                                    await redis_manager.add_to_active(job.task_id)
                                    logger.info(f"⬇️ Download started for task: {job.task_id} (Job: {job.job_id})")
                                    
                                    asyncio.create_task(
                                        self._execute_download(job, task)
                                    )
                                else:
                                    logger.error(f"Task not found: {job.task_id}")
                                    await job_queue.mark_failed(job.job_id, "Task not found")
                            finally:
                                db.close()
                    
                    # Reset error count on successful dequeue
                    if self.error_count > 0:
                        self.error_count -= 1
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                self.error_count += 1
                self.last_error = str(e)
                logger.error(f"Queue processor error ({self.error_count}/{self.max_errors}): {e}")
                
                if self.error_count >= self.max_errors:
                    logger.critical(f"🔴 Max errors reached, queue worker shutting down")
                    self.running = False
                    break
                
                await asyncio.sleep(5)
    
    async def _execute_download(self, job, task):
        """Execute a download with error handling and tracking"""
        start_time = datetime.utcnow()
        
        try:
            await progress_tracker.start_download(job.task_id, None)
            
            # Execute the download
            await download_service.download(job.task_id)
            
            # Mark as completed
            await job_queue.mark_completed(job.job_id, {
                "file_path": task.file_path,
                "file_size": task.file_size
            })
            
            self.worker_stats["tasks_succeeded"] += 1
            logger.info(f"✅ Download completed: {job.task_id}")
            
        except asyncio.CancelledError:
            await progress_tracker.mark_cancelled(job.task_id)
            await job_queue.mark_cancelled(job.job_id)
            logger.info(f"⏹️ Download cancelled: {job.task_id}")
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:200]}"
            await progress_tracker.mark_failed(job.task_id, error_msg)
            
            # Determine if we should retry
            should_retry = isinstance(e, (asyncio.TimeoutError, ConnectionError))
            await job_queue.mark_failed(job.job_id, error_msg, should_retry)
            
            self.worker_stats["tasks_failed"] += 1
            logger.error(f"❌ Download failed: {job.task_id} - {error_msg}")
            
        finally:
            # Cleanup
            await redis_manager.remove_from_active(job.task_id)
            self.worker_stats["tasks_processed"] += 1
            
            # Calculate runtime
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.worker_stats["total_runtime"] += duration
    
    async def cleanup_old_tasks(self):
        """Clean up old completed/failed tasks and files"""
        logger.info("🧹 Cleanup worker started")
        
        while self.running:
            db = None
            try:
                db = next(get_db())
                cutoff = datetime.utcnow() - timedelta(seconds=settings.AUTO_DELETE_AFTER)
                
                # Find old tasks
                old_tasks = db.query(DownloadTask).filter(
                    and_(
                        DownloadTask.status.in_(["completed", "failed", "cancelled"]),
                        DownloadTask.updated_at < cutoff
                    )
                ).limit(100).all()  # Process in batches
                
                if old_tasks:
                    logger.info(f"Cleaning up {len(old_tasks)} old tasks")
                    
                    for task in old_tasks:
                        try:
                            # Delete file if exists
                            if task.file_path:
                                file_path = Path(task.file_path).resolve()
                                download_dir = Path(settings.DOWNLOAD_DIR).resolve()
                                
                                if str(file_path).startswith(str(download_dir)):
                                    if file_path.exists():
                                        file_path.unlink()
                                        logger.debug(f"Deleted file: {file_path.name}")
                                else:
                                    logger.warning(f"File outside download directory: {file_path}")
                            
                            # Clean progress data
                            await progress_tracker.cleanup_progress(task.id)
                            
                            # Delete task record
                            db.delete(task)
                        except Exception as e:
                            logger.error(f"Error cleaning task {task.id}: {e}")
                    
                    db.commit()
                    logger.info(f"✅ Cleaned up {len(old_tasks)} tasks")
                
                await asyncio.sleep(600)  # Run every 10 minutes
                
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                await asyncio.sleep(600)
            finally:
                if db:
                    try:
                        db.close()
                    except Exception:
                        pass
    
    async def health_check_loop(self):
        """Monitor worker health and performance"""
        logger.info("💚 Health check loop started")
        
        while self.running:
            try:
                # Check Redis
                redis_ok = await redis_manager.ping()
                
                if not redis_ok:
                    logger.warning("⚠️ Redis health check failed")
                    # Try to reconnect
                    try:
                        await redis_manager.connect()
                    except Exception as e:
                        logger.error(f"Failed to reconnect to Redis: {e}")
                
                # Log stats every 5 minutes
                active = await redis_manager.get_active_count()
                queued = await redis_manager.get_queue_size()
                
                logger.info(
                    f"📊 Queue stats - Active: {active}, "
                    f"Queued: {queued}, "
                    f"Processed: {self.worker_stats['tasks_processed']}, "
                    f"Success rate: {self.worker_stats['tasks_succeeded']}/{self.worker_stats['tasks_processed']}"
                )
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(300)
    
    async def job_queue_monitor(self):
        """Monitor job queue health and performance"""
        logger.info("📈 Job queue monitor started")
        
        while self.running:
            try:
                stats = await job_queue.get_stats()
                logger.debug(f"Job queue stats: {stats}")
                
                # Alert if queue is backing up
                if stats["queued"] > 50:
                    logger.warning(f"⚠️ Large queue backlog: {stats['queued']} jobs queued")
                
                # Clean up old jobs every hour
                removed = job_queue.cleanup_old_jobs(max_age_hours=24)
                if removed > 0:
                    logger.info(f"Cleaned up {removed} old jobs")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Job queue monitor error: {e}")
                await asyncio.sleep(60)
    
    def get_stats(self) -> dict:
        """Get worker statistics"""
        uptime = (datetime.utcnow() - self.worker_stats["uptime_start"]).total_seconds()
        avg_duration = (
            self.worker_stats["total_runtime"] / self.worker_stats["tasks_processed"]
            if self.worker_stats["tasks_processed"] > 0 else 0
        )
        
        return {
            "running": self.running,
            "tasks_processed": self.worker_stats["tasks_processed"],
            "tasks_succeeded": self.worker_stats["tasks_succeeded"],
            "tasks_failed": self.worker_stats["tasks_failed"],
            "success_rate": (
                (self.worker_stats["tasks_succeeded"] / self.worker_stats["tasks_processed"] * 100)
                if self.worker_stats["tasks_processed"] > 0 else 0
            ),
            "average_duration": avg_duration,
            "total_runtime": self.worker_stats["total_runtime"],
            "uptime": uptime,
            "error_count": self.error_count,
            "last_error": self.last_error
        }

# Global instance
queue_worker = OptimizedQueueWorker()
