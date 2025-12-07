"""Progress tracking and monitoring endpoints"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from core.validation import UUIDValidator
from core.security import get_optional_api_key, is_feature_enabled
from core.error_handler import ErrorContext
from core.exceptions import TaskNotFoundError
from infrastructure.progress_tracker import progress_tracker
from infrastructure.database import get_db, DownloadTask

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/progress", tags=["progress"])

class ProgressInfo(BaseModel):
    """Progress information response"""
    task_id: str
    url: str
    title: Optional[str]
    status: str
    progress: float
    current_bytes: int
    total_bytes: int
    speed_bps: float
    eta_seconds: Optional[float]
    filename: Optional[str]
    file_size: Optional[int]
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]

class ProgressEvent(BaseModel):
    """Progress event"""
    event: str
    timestamp: str
    details: dict

class ProgressSummary(BaseModel):
    """Overall progress summary"""
    task_id: str
    status: str
    progress: float
    speed_bps: float
    eta_seconds: Optional[float]
    time_remaining: Optional[str]

class MultiTaskProgress(BaseModel):
    """Multiple tasks progress"""
    total_tasks: int
    completed: int
    downloading: int
    failed: int
    cancelled: int
    pending: int
    overall_progress: float
    tasks: list

@router.get("/tasks/{task_id}", response_model=ProgressInfo)
async def get_task_progress(
    task_id: str,
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get detailed progress for a specific task"""
    
    with ErrorContext("get_task_progress", task_id=task_id):
        # Validate task ID
        task_id = UUIDValidator.validate_or_raise(task_id)
        
        # Get progress from Redis
        progress_data = await progress_tracker.get_progress(task_id)
        
        logger.info(f"Progress retrieved for task {task_id}")
        
        return ProgressInfo(**progress_data)

@router.get("/tasks/{task_id}/summary", response_model=ProgressSummary)
async def get_task_summary(
    task_id: str,
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get progress summary for a task"""
    
    with ErrorContext("get_task_summary", task_id=task_id):
        task_id = UUIDValidator.validate_or_raise(task_id)
        
        progress_data = await progress_tracker.get_progress(task_id)
        
        # Format time remaining
        eta_seconds = progress_data.get("eta_seconds")
        time_remaining = None
        if eta_seconds:
            hours, remainder = divmod(int(eta_seconds), 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                time_remaining = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                time_remaining = f"{minutes}m {seconds}s"
            else:
                time_remaining = f"{seconds}s"
        
        return ProgressSummary(
            task_id=task_id,
            status=progress_data["status"],
            progress=progress_data["progress"],
            speed_bps=progress_data.get("speed_bps", 0.0),
            eta_seconds=eta_seconds,
            time_remaining=time_remaining
        )

@router.get("/tasks/{task_id}/events", response_model=list[ProgressEvent])
async def get_task_events(
    task_id: str,
    limit: int = Query(100, ge=1, le=500),
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get progress events for a task"""
    
    with ErrorContext("get_task_events", task_id=task_id):
        task_id = UUIDValidator.validate_or_raise(task_id)
        
        # Verify task exists
        progress_data = await progress_tracker.get_progress(task_id)
        
        # Get events
        events = await progress_tracker.get_events(task_id, limit)
        
        logger.info(f"Retrieved {len(events)} events for task {task_id}")
        
        return [ProgressEvent(**event) for event in events]

@router.get("/tasks", response_model=MultiTaskProgress)
async def get_all_progress(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get progress for all tasks"""
    
    with ErrorContext("get_all_progress"):
        # Get all tasks from database
        query = db.query(DownloadTask)
        
        if status:
            valid_statuses = ["pending", "downloading", "completed", "failed", "cancelled", "processing"]
            if status not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
            query = query.filter(DownloadTask.status == status)
        
        tasks = query.order_by(DownloadTask.created_at.desc()).limit(limit).all()
        
        # Get progress for each task
        task_progresses = []
        total_progress = 0.0
        
        status_counts = {
            "completed": 0,
            "downloading": 0,
            "processing": 0,
            "failed": 0,
            "cancelled": 0,
            "pending": 0
        }
        
        for task in tasks:
            try:
                progress_data = await progress_tracker.get_progress(str(task.id))
                task_status = progress_data.get("status", task.status)
                task_progress = progress_data.get("progress", 0.0)
                
                total_progress += task_progress
                
                if task_status in status_counts:
                    status_counts[task_status] += 1
                
                task_progresses.append({
                    "task_id": str(task.id),
                    "title": progress_data.get("title"),
                    "status": task_status,
                    "progress": task_progress,
                    "speed_bps": progress_data.get("speed_bps", 0.0)
                })
            except Exception as e:
                logger.warning(f"Error getting progress for task {task.id}: {e}")
        
        # Calculate overall progress
        overall_progress = (total_progress / len(tasks)) if tasks else 0.0
        
        logger.info(f"Retrieved progress for {len(tasks)} tasks")
        
        return MultiTaskProgress(
            total_tasks=len(tasks),
            completed=status_counts["completed"],
            downloading=status_counts["downloading"],
            failed=status_counts["failed"],
            cancelled=status_counts["cancelled"],
            pending=status_counts["pending"],
            overall_progress=overall_progress,
            tasks=task_progresses
        )

@router.get("/stats")
async def get_progress_stats(
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get progress statistics"""
    
    with ErrorContext("get_progress_stats"):
        from sqlalchemy import func
        
        # Get task statistics
        stats = db.query(
            DownloadTask.status,
            func.count(DownloadTask.id).label('count'),
            func.avg(DownloadTask.progress).label('avg_progress'),
            func.max(DownloadTask.progress).label('max_progress')
        ).group_by(DownloadTask.status).all()
        
        stats_dict = {}
        total_tasks = 0
        total_progress = 0.0
        
        for status, count, avg_progress, max_progress in stats:
            stats_dict[status] = {
                "count": count,
                "avg_progress": float(avg_progress) if avg_progress else 0.0,
                "max_progress": float(max_progress) if max_progress else 0.0
            }
            total_tasks += count
            if avg_progress:
                total_progress += avg_progress * count
        
        overall_progress = (total_progress / total_tasks) if total_tasks > 0 else 0.0
        
        return {
            "total_tasks": total_tasks,
            "overall_progress": overall_progress,
            "by_status": stats_dict
        }

@router.get("/bandwidth")
async def get_bandwidth_stats(
    minutes: int = Query(5, ge=1, le=60),
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get bandwidth statistics"""
    
    with ErrorContext("get_bandwidth_stats"):
        # Get all currently downloading tasks
        downloading_tasks = db.query(DownloadTask).filter(
            DownloadTask.status == "downloading"
        ).all()
        
        total_speed = 0.0
        downloading_count = 0
        
        for task in downloading_tasks:
            try:
                progress_data = await progress_tracker.get_progress(str(task.id))
                speed = progress_data.get("speed_bps", 0.0)
                total_speed += speed
                downloading_count += 1
            except Exception:
                pass
        
        # Convert bytes per second to human-readable format
        def format_speed(bps: float) -> str:
            if bps < 1024:
                return f"{bps:.0f} B/s"
            elif bps < 1024 ** 2:
                return f"{bps / 1024:.2f} KB/s"
            elif bps < 1024 ** 3:
                return f"{bps / (1024 ** 2):.2f} MB/s"
            else:
                return f"{bps / (1024 ** 3):.2f} GB/s"
        
        return {
            "downloading_count": downloading_count,
            "total_speed_bps": total_speed,
            "total_speed_formatted": format_speed(total_speed),
            "average_speed_bps": total_speed / downloading_count if downloading_count > 0 else 0.0,
            "average_speed_formatted": format_speed(total_speed / downloading_count) if downloading_count > 0 else "0 B/s"
        }
