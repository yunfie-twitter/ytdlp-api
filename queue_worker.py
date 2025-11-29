import asyncio
from datetime import datetime, timedelta
from sqlalchemy import and_

from redis_manager import redis_manager
from download_service import download_service
from database import get_db, DownloadTask
from config import settings

class QueueWorker:
    def __init__(self):
        self.running = False
    
    async def start(self):
        """Start the queue worker"""
        self.running = True
        await asyncio.gather(
            self.process_queue(),
            self.cleanup_old_tasks()
        )
    
    async def stop(self):
        """Stop the queue worker"""
        self.running = False
    
    async def process_queue(self):
        """Process pending downloads from queue"""
        while self.running:
            try:
                # Check if we can start new download
                if await redis_manager.can_start_download():
                    # Get next pending task
                    task_id = await redis_manager.get_next_pending()
                    
                    if task_id:
                        # Mark as active
                        await redis_manager.add_to_active(task_id)
                        
                        # Start download in background
                        asyncio.create_task(download_service.download(task_id))
                
                # Wait before checking again
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Queue worker error: {e}")
                await asyncio.sleep(5)
    
    async def cleanup_old_tasks(self):
        """Clean up old completed/failed tasks"""
        while self.running:
            try:
                db = next(get_db())
                
                # Calculate cutoff time
                cutoff = datetime.utcnow() - timedelta(seconds=settings.AUTO_DELETE_AFTER)
                
                # Find old completed/failed tasks
                old_tasks = db.query(DownloadTask).filter(
                    and_(
                        DownloadTask.status.in_(["completed", "failed", "cancelled"]),
                        DownloadTask.updated_at < cutoff
                    )
                ).all()
                
                for task in old_tasks:
                    # Delete file if exists
                    if task.file_path:
                        try:
                            import os
                            if os.path.exists(task.file_path):
                                os.remove(task.file_path)
                        except Exception as e:
                            print(f"Failed to delete file {task.file_path}: {e}")
                    
                    # Delete from database
                    db.delete(task)
                
                db.commit()
                db.close()
                
                # Run cleanup every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                print(f"Cleanup worker error: {e}")
                await asyncio.sleep(300)

queue_worker = QueueWorker()