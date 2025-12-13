"""Worker for processing media conversion tasks"""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import and_

from core.error_handling import ErrorContext
from core.config import settings
from infrastructure.redis_manager import redis_manager
from infrastructure.progress_tracker import progress_tracker
from services.conversion_service import conversion_service
from services.conversion_queue import conversion_queue
from infrastructure.database import get_db, ConversionTask
from infrastructure.conversion_models import ConversionStatus

logger = logging.getLogger(__name__)


class ConversionWorker:
    """Worker for processing conversion queue with priority scheduling"""
    
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
        # Configuration
        self.max_concurrent_conversions = getattr(settings, "MAX_CONCURRENT_CONVERSIONS", 2)
        self.gpu_enabled = getattr(settings, "ENABLE_GPU_ENCODING", False)
    
    async def start(self):
        """Start all conversion worker components"""
        logger.info("🚀 Starting conversion worker")
        logger.info(f"Max concurrent conversions: {self.max_concurrent_conversions}")
        logger.info(f"GPU encoding: {'Enabled' if self.gpu_enabled else 'Disabled'}")
        
        self.running = True
        self.worker_stats["uptime_start"] = datetime.utcnow()
        
        try:
            await asyncio.gather(
                self.process_queue(),
                self.cleanup_old_tasks(),
                self.health_check_loop(),
                self.queue_monitor(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"💥 Fatal error in conversion worker: {e}", exc_info=True)
            self.running = False
    
    async def stop(self):
        """Stop all worker components gracefully"""
        logger.info("🛑 Stopping conversion worker")
        self.running = False
        
        tasks = [self.queue_task, self.cleanup_task, self.health_check_task]
        for task in tasks:
            if task:
                try:
                    await asyncio.wait_for(task, timeout=5)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    logger.warning(f"Task did not stop gracefully: {task}")
        
        logger.info(
            f"📊 Final stats - Processed: {self.worker_stats['tasks_processed']}, "
            f"Succeeded: {self.worker_stats['tasks_succeeded']}, "
            f"Failed: {self.worker_stats['tasks_failed']}"
        )
    
    async def process_queue(self):
        """Process pending conversions with priority scheduling"""
        logger.info("📋 Conversion queue processor started")
        
        while self.running:
            try:
                # Check if we can start more conversions
                active_count = await conversion_queue.get_active_count()
                queue_size = await conversion_queue.get_queue_size()
                
                if active_count < self.max_concurrent_conversions and queue_size > 0:
                    # Get next job from priority queue
                    job = await conversion_queue.dequeue()
                    
                    if job:
                        task_id = job.get("task_id")
                        with ErrorContext("process_conversion", task_id=task_id):
                            db = next(get_db())
                            try:
                                task = db.query(ConversionTask).filter(
                                    ConversionTask.id == task_id
                                ).first()
                                
                                if task:
                                    # Initialize progress tracking
                                    await progress_tracker.initialize_task(
                                        task_id,
                                        f"{task.source_format.upper()} → {task.target_format.upper()}",
                                        task.title or "Conversion Task"
                                    )
                                    
                                    # Mark as active
                                    await conversion_queue.mark_active(task_id)
                                    await redis_manager.add_to_active(task_id)
                                    
                                    logger.info(
                                        f"⬇️ Conversion started for task: {task_id} "
                                        f"({task.source_format}→{task.target_format})"
                                    )
                                    
                                    # Start conversion in background
                                    asyncio.create_task(
                                        self._execute_conversion(job, task)
                                    )
                                else:
                                    logger.error(f"Conversion task not found: {task_id}")
                                    await conversion_queue.mark_failed(
                                        task_id,
                                        "Conversion task not found in database",
                                        should_retry=False
                                    )
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
                    logger.critical(f"🔴 Max errors reached, conversion worker shutting down")
                    self.running = False
                    break
                
                await asyncio.sleep(5)
    
    async def _execute_conversion(self, job, task):
        """Execute a conversion task with error handling"""
        start_time = datetime.utcnow()
        task_id = job.get("task_id")
        
        try:
            await progress_tracker.start_download(task_id, None)
            
            # Execute the conversion
            logger.info(f"Converting {task_id}: {task.source_file_path}")
            await conversion_service.convert(
                task_id,
                gpu_enabled=self.gpu_enabled
            )
            
            # Check status from DB
            db = next(get_db())
            try:
                updated_task = db.query(ConversionTask).filter(
                    ConversionTask.id == task_id
                ).first()
                
                if updated_task and updated_task.status == ConversionStatus.COMPLETED:
                    await conversion_queue.mark_completed(
                        task_id,
                        {
                            "output_file": updated_task.output_filename,
                            "output_size": updated_task.output_file_size
                        }
                    )
                    self.worker_stats["tasks_succeeded"] += 1
                    logger.info(f"✅ Conversion completed: {task_id}")
                else:
                    # Failed during conversion
                    error_msg = updated_task.error_message if updated_task else "Unknown error"
                    await conversion_queue.mark_failed(
                        task_id,
                        error_msg,
                        should_retry=(job.get("retry_count", 0) < job.get("max_retries", 3))
                    )
                    self.worker_stats["tasks_failed"] += 1
                    logger.error(f"❌ Conversion failed: {task_id} - {error_msg}")
            finally:
                db.close()
            
        except asyncio.CancelledError:
            await progress_tracker.mark_cancelled(task_id)
            await conversion_queue.mark_cancelled(task_id)
            logger.info(f"⏹️ Conversion cancelled: {task_id}")
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:200]}"
            await progress_tracker.mark_failed(task_id, error_msg)
            
            # Determine if we should retry
            should_retry = isinstance(e, (asyncio.TimeoutError, ConnectionError))
            await conversion_queue.mark_failed(
                task_id,
                error_msg,
                should_retry=should_retry
            )
            
            self.worker_stats["tasks_failed"] += 1
            logger.error(f"❌ Conversion failed: {task_id} - {error_msg}")
            
        finally:
            # Cleanup
            await redis_manager.remove_from_active(task_id)
            self.worker_stats["tasks_processed"] += 1
            
            # Calculate runtime
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.worker_stats["total_runtime"] += duration
    
    async def cleanup_old_tasks(self):
        """Clean up old completed/failed conversion tasks"""
        logger.info("🧹 Cleanup worker started")
        
        while self.running:
            db = None
            try:
                db = next(get_db())
                cutoff = datetime.utcnow() - timedelta(seconds=getattr(settings, "AUTO_DELETE_AFTER", 604800))
                
                # Find old tasks
                old_tasks = db.query(ConversionTask).filter(
                    and_(
                        ConversionTask.status.in_([
                            ConversionStatus.COMPLETED,
                            ConversionStatus.FAILED,
                            ConversionStatus.CANCELLED
                        ]),
                        ConversionTask.updated_at < cutoff
                    )
                ).limit(100).all()
                
                if old_tasks:
                    logger.info(f"Cleaning up {len(old_tasks)} old conversion tasks")
                    
                    for task in old_tasks:
                        try:
                            # Delete output file if exists
                            if task.output_file_path:
                                file_path = Path(task.output_file_path).resolve()
                                download_dir = Path(settings.DOWNLOAD_DIR).resolve()
                                
                                if str(file_path).startswith(str(download_dir)):
                                    if file_path.exists():
                                        file_path.unlink()
                                        logger.debug(f"Deleted conversion output: {file_path.name}")
                                else:
                                    logger.warning(f"File outside download directory: {file_path}")
                            
                            # Clean progress data
                            await progress_tracker.cleanup_progress(task.id)
                            
                            # Delete task record
                            db.delete(task)
                        except Exception as e:
                            logger.error(f"Error cleaning task {task.id}: {e}")
                    
                    db.commit()
                    logger.info(f"✅ Cleaned up {len(old_tasks)} conversion tasks")
                
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
        logger.info("💚 Conversion health check loop started")
        
        while self.running:
            try:
                # Check Redis
                redis_ok = await redis_manager.ping()
                
                if not redis_ok:
                    logger.warning("⚠️ Redis health check failed")
                    try:
                        await redis_manager.connect()
                    except Exception as e:
                        logger.error(f"Failed to reconnect to Redis: {e}")
                
                # Log stats every 5 minutes
                active = await conversion_queue.get_active_count()
                queued = await conversion_queue.get_queue_size()
                stats = await conversion_queue.get_stats()
                
                success_rate = (
                    (self.worker_stats["tasks_succeeded"] / self.worker_stats["tasks_processed"] * 100)
                    if self.worker_stats["tasks_processed"] > 0 else 0
                )
                
                logger.info(
                    f"📊 Conversion queue stats - "
                    f"Active: {active}/{self.max_concurrent_conversions}, "
                    f"Queued: {queued}, "
                    f"Processed: {self.worker_stats['tasks_processed']}, "
                    f"Success rate: {success_rate:.1f}%, "
                    f"Total: {stats}"
                )
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(300)
    
    async def queue_monitor(self):
        """Monitor conversion queue health"""
        logger.info("📈 Conversion queue monitor started")
        
        while self.running:
            try:
                stats = await conversion_queue.get_stats()
                logger.debug(f"Conversion queue stats: {stats}")
                
                # Alert if queue is backing up
                if stats.get("queued", 0) > 20:
                    logger.warning(
                        f"⚠️ Large conversion queue backlog: {stats['queued']} tasks queued"
                    )
                
                # Clean up old jobs every hour
                removed = conversion_queue.cleanup_old_jobs(max_age_hours=24)
                if removed > 0:
                    logger.info(f"Cleaned up {removed} old conversion jobs")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Queue monitor error: {e}")
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
            "last_error": self.last_error,
            "max_concurrent_conversions": self.max_concurrent_conversions
        }


# Global instance
conversion_worker = ConversionWorker()
