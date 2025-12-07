"""Progress tracking and monitoring for download tasks"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import asyncio

from infrastructure.redis_manager import redis_manager
from infrastructure.database import get_db, DownloadTask
from core.exceptions import TaskNotFoundError, InternalServerError

logger = logging.getLogger(__name__)

class ProgressStatus(str, Enum):
    """Task progress status enumeration"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ProgressEvent(str, Enum):
    """Progress event types"""
    CREATED = "task_created"
    STARTED = "download_started"
    PROGRESS = "progress_update"
    PROCESSING = "post_processing"
    COMPLETED = "task_completed"
    FAILED = "task_failed"
    CANCELLED = "task_cancelled"

class ProgressTracker:
    """Tracks and manages task progress"""
    
    def __init__(self):
        self.redis_prefix = "progress:"
        self.event_prefix = "events:"
        self.speed_samples = {}  # Track download speed
    
    async def initialize_task(self, task_id: str, url: str, title: Optional[str] = None) -> dict:
        """Initialize progress tracking for a new task"""
        try:
            progress_data = {
                "task_id": task_id,
                "url": url,
                "title": title or "Unknown",
                "status": ProgressStatus.PENDING.value,
                "progress": 0.0,
                "current_bytes": 0,
                "total_bytes": 0,
                "speed_bps": 0.0,
                "eta_seconds": None,
                "events": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None,
                "completed_at": None,
                "error_message": None
            }
            
            # Store in Redis
            await redis_manager.set(
                f"{self.redis_prefix}{task_id}",
                progress_data,
                ex=86400 * 7  # 7 days TTL
            )
            
            # Record event
            await self._record_event(
                task_id,
                ProgressEvent.CREATED,
                {"title": title, "url": url[:60]}
            )
            
            logger.info(f"Progress tracking initialized for task {task_id}")
            return progress_data
        except Exception as e:
            logger.error(f"Error initializing progress for task {task_id}: {e}")
            raise InternalServerError(
                f"Failed to initialize progress tracking: {str(e)}",
                details={"task_id": task_id}
            )
    
    async def start_download(self, task_id: str, process_id: int) -> bool:
        """Mark download as started"""
        try:
            progress_data = await redis_manager.get(f"{self.redis_prefix}{task_id}")
            if not progress_data:
                logger.warning(f"Progress data not found for task {task_id}")
                return False
            
            progress_data["status"] = ProgressStatus.DOWNLOADING.value
            progress_data["started_at"] = datetime.now(timezone.utc).isoformat()
            progress_data["process_id"] = process_id
            
            await redis_manager.set(
                f"{self.redis_prefix}{task_id}",
                progress_data,
                ex=86400 * 7
            )
            
            await self._record_event(
                task_id,
                ProgressEvent.STARTED,
                {"process_id": process_id}
            )
            
            logger.info(f"Download started for task {task_id} (PID: {process_id})")
            return True
        except Exception as e:
            logger.error(f"Error starting download for task {task_id}: {e}")
            return False
    
    async def update_progress(
        self,
        task_id: str,
        progress: float,
        current_bytes: int = 0,
        total_bytes: int = 0,
        speed_bps: float = 0.0
    ) -> bool:
        """Update task progress"""
        try:
            progress_data = await redis_manager.get(f"{self.redis_prefix}{task_id}")
            if not progress_data:
                logger.warning(f"Progress data not found for task {task_id}")
                return False
            
            # Clamp progress between 0 and 100
            progress = max(0.0, min(100.0, progress))
            
            progress_data["progress"] = progress
            progress_data["current_bytes"] = current_bytes
            progress_data["total_bytes"] = total_bytes
            progress_data["speed_bps"] = speed_bps
            
            # Calculate ETA
            if total_bytes > 0 and speed_bps > 0:
                remaining_bytes = total_bytes - current_bytes
                eta_seconds = remaining_bytes / speed_bps
                progress_data["eta_seconds"] = eta_seconds
            else:
                progress_data["eta_seconds"] = None
            
            progress_data["last_update"] = datetime.now(timezone.utc).isoformat()
            
            await redis_manager.set(
                f"{self.redis_prefix}{task_id}",
                progress_data,
                ex=86400 * 7
            )
            
            # Record event every 10% or on significant speed change
            if progress % 10 == 0 or progress == 100:
                await self._record_event(
                    task_id,
                    ProgressEvent.PROGRESS,
                    {
                        "progress": progress,
                        "speed_bps": speed_bps,
                        "current_bytes": current_bytes,
                        "total_bytes": total_bytes
                    }
                )
            
            return True
        except Exception as e:
            logger.error(f"Error updating progress for task {task_id}: {e}")
            return False
    
    async def mark_processing(self, task_id: str) -> bool:
        """Mark task as in post-processing phase"""
        try:
            progress_data = await redis_manager.get(f"{self.redis_prefix}{task_id}")
            if not progress_data:
                return False
            
            progress_data["status"] = ProgressStatus.PROCESSING.value
            progress_data["progress"] = 95.0  # Almost done
            
            await redis_manager.set(
                f"{self.redis_prefix}{task_id}",
                progress_data,
                ex=86400 * 7
            )
            
            await self._record_event(
                task_id,
                ProgressEvent.PROCESSING,
                {"phase": "post-processing"}
            )
            
            logger.info(f"Task {task_id} entering post-processing phase")
            return True
        except Exception as e:
            logger.error(f"Error marking processing for task {task_id}: {e}")
            return False
    
    async def mark_completed(
        self,
        task_id: str,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None
    ) -> bool:
        """Mark task as completed"""
        try:
            progress_data = await redis_manager.get(f"{self.redis_prefix}{task_id}")
            if not progress_data:
                return False
            
            progress_data["status"] = ProgressStatus.COMPLETED.value
            progress_data["progress"] = 100.0
            progress_data["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            if file_path:
                progress_data["file_path"] = file_path
            if file_size:
                progress_data["file_size"] = file_size
            
            await redis_manager.set(
                f"{self.redis_prefix}{task_id}",
                progress_data,
                ex=86400 * 7
            )
            
            await self._record_event(
                task_id,
                ProgressEvent.COMPLETED,
                {"file_path": file_path, "file_size": file_size}
            )
            
            logger.info(f"Task {task_id} completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error marking completed for task {task_id}: {e}")
            return False
    
    async def mark_failed(self, task_id: str, error_message: str) -> bool:
        """Mark task as failed"""
        try:
            progress_data = await redis_manager.get(f"{self.redis_prefix}{task_id}")
            if not progress_data:
                return False
            
            progress_data["status"] = ProgressStatus.FAILED.value
            progress_data["completed_at"] = datetime.now(timezone.utc).isoformat()
            progress_data["error_message"] = error_message[:500]
            
            await redis_manager.set(
                f"{self.redis_prefix}{task_id}",
                progress_data,
                ex=86400 * 7
            )
            
            await self._record_event(
                task_id,
                ProgressEvent.FAILED,
                {"error": error_message[:100]}
            )
            
            logger.error(f"Task {task_id} failed: {error_message[:100]}")
            return True
        except Exception as e:
            logger.error(f"Error marking failed for task {task_id}: {e}")
            return False
    
    async def mark_cancelled(self, task_id: str) -> bool:
        """Mark task as cancelled"""
        try:
            progress_data = await redis_manager.get(f"{self.redis_prefix}{task_id}")
            if not progress_data:
                return False
            
            progress_data["status"] = ProgressStatus.CANCELLED.value
            progress_data["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            await redis_manager.set(
                f"{self.redis_prefix}{task_id}",
                progress_data,
                ex=86400 * 7
            )
            
            await self._record_event(
                task_id,
                ProgressEvent.CANCELLED,
                {}
            )
            
            logger.info(f"Task {task_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error marking cancelled for task {task_id}: {e}")
            return False
    
    async def get_progress(self, task_id: str) -> dict:
        """Get current task progress"""
        try:
            progress_data = await redis_manager.get(f"{self.redis_prefix}{task_id}")
            if not progress_data:
                raise TaskNotFoundError(task_id)
            
            # Also get database data for completeness
            db = next(get_db())
            try:
                task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
                if task:
                    progress_data["filename"] = task.filename
                    progress_data["file_size"] = task.file_size
                    progress_data["error_message"] = task.error_message
            finally:
                db.close()
            
            return progress_data
        except TaskNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting progress for task {task_id}: {e}")
            raise InternalServerError(
                f"Failed to retrieve progress: {str(e)}",
                details={"task_id": task_id}
            )
    
    async def get_events(self, task_id: str, limit: int = 100) -> list:
        """Get task events"""
        try:
            events_key = f"{self.event_prefix}{task_id}"
            events = await redis_manager.get(events_key)
            return events[-limit:] if events else []
        except Exception as e:
            logger.error(f"Error getting events for task {task_id}: {e}")
            return []
    
    async def _record_event(
        self,
        task_id: str,
        event_type: ProgressEvent,
        details: Dict[str, Any]
    ) -> bool:
        """Record a progress event"""
        try:
            event = {
                "event": event_type.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details
            }
            
            events_key = f"{self.event_prefix}{task_id}"
            events = await redis_manager.get(events_key) or []
            events.append(event)
            
            # Keep only last 100 events
            events = events[-100:]
            
            await redis_manager.set(
                events_key,
                events,
                ex=86400 * 7
            )
            
            return True
        except Exception as e:
            logger.error(f"Error recording event for task {task_id}: {e}")
            return False
    
    async def cleanup_progress(self, task_id: str) -> bool:
        """Clean up progress tracking data"""
        try:
            await redis_manager.delete(f"{self.redis_prefix}{task_id}")
            await redis_manager.delete(f"{self.event_prefix}{task_id}")
            logger.info(f"Cleaned up progress data for task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error cleaning up progress for task {task_id}: {e}")
            return False

# Global instance
progress_tracker = ProgressTracker()
