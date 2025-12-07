"""Queue worker for managing download tasks"""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import and_

from infrastructure.redis_manager import redis_manager
from services.download_service import download_service
from infrastructure.database import get_db, DownloadTask
from core.config import settings

logger = logging.getLogger(__name__)

class QueueWorker:
    """Manages download queue and cleanup tasks"""
    def __init__(self):
        self.running = False
        self.queue_task = None
        self.cleanup_task = None
    
    async def start(self):
        """Start the queue worker"""
        logger.info("🚀 Starting queue worker")
        self.running = True
        try:
            await asyncio.gather(
                self.process_queue(),
                self.cleanup_old_tasks(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Fatal error in queue worker: {e}", exc_info=True)
    
    async def stop(self):
        """Stop the queue worker"""
        logger.info("🛑 Stopping queue worker")
        self.running = False
        
        if self.queue_task:
            try:
                await asyncio.wait_for(self.queue_task, timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Queue task did not stop gracefully")
        
        if self.cleanup_task:
            try:
                await asyncio.wait_for(self.cleanup_task, timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Cleanup task did not stop gracefully")
    
    async def process_queue(self):
        """Process pending downloads from queue"""
        logger.info("📋 Queue processor started")
        error_count = 0
        max_errors = 10
        
        while self.running:
            try:
                can_start = await redis_manager.can_start_download()
                
                if can_start:
                    task_id = await redis_manager.get_next_pending()
                    
                    if task_id:
                        try:
                            await redis_manager.add_to_active(task_id)
                            logger.info(f"⬇️ Download started for task: {task_id}")
                            asyncio.create_task(download_service.download(task_id))
                        except Exception as e:
                            logger.error(f"Error starting download for {task_id}: {e}")
                            await redis_manager.remove_from_active(task_id)
                
                await asyncio.sleep(2)
                
                if error_count > 0:
                    error_count -= 1
                
            except Exception as e:
                error_count += 1
                logger.error(f"Queue worker error (count: {error_count}/{max_errors}): {e}", exc_info=True)
                
                if error_count >= max_errors:
                    logger.critical(f"Queue worker exceeded max errors, shutting down")
                    self.running = False
                    break
                
                await asyncio.sleep(5)
    
    async def cleanup_old_tasks(self):
        """Clean up old completed/failed tasks"""
        logger.info("🧹 Cleanup worker started")
        
        while self.running:
            db = None
            try:
                db = next(get_db())
                
                cutoff = datetime.utcnow() - timedelta(seconds=settings.AUTO_DELETE_AFTER)
                
                old_tasks = db.query(DownloadTask).filter(
                    and_(
                        DownloadTask.status.in_(["completed", "failed", "cancelled"]),
                        DownloadTask.updated_at < cutoff
                    )
                ).all()
                
                if old_tasks:
                    logger.info(f"Cleaning up {len(old_tasks)} old tasks")
                    
                    for task in old_tasks:
                        try:
                            if task.file_path:
                                file_path = Path(task.file_path).resolve()
                                download_dir = Path(settings.DOWNLOAD_DIR).resolve()
                                
                                if str(file_path).startswith(str(download_dir)):
                                    if file_path.exists():
                                        file_path.unlink()
                                        logger.info(f"Deleted file for task {task.id}: {file_path.name}")
                                else:
                                    logger.warning(f"File path outside download directory: {file_path}")
                            
                            db.delete(task)
                        except Exception as e:
                            logger.error(f"Error cleaning up task {task.id}: {e}")
                    
                    db.commit()
                    logger.info(f"Cleaned up {len(old_tasks)} tasks")
                
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}", exc_info=True)
                await asyncio.sleep(300)
            finally:
                if db:
                    try:
                        db.close()
                    except Exception as e:
                        logger.error(f"Error closing database: {e}")

queue_worker = QueueWorker()
