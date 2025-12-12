"""API endpoints with comprehensive error handling and JWT authentication"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request, Query

from core.config import settings
from core import check_rate_limit, is_feature_enabled, get_optional_api_key, ErrorContext
from core.exceptions import (
    TaskNotFoundError,
    InvalidStateError,
    FileAccessError,
    PathTraversalError,
    DownloadTimeoutError,
    VideoInfoError
)
from core.validation import InputValidator, UUIDValidator
from app.models import (
    DownloadRequest, TaskResponse, TaskStatusResponse, VideoInfoResponse
)
from infrastructure.database import get_db, DownloadTask
from infrastructure.redis_manager import redis_manager
from infrastructure.websocket_manager import ws_manager
from services.download_service import download_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["downloads"])

# Helper function to check if feature is enabled
def require_feature(feature_name: str):
    """Check if feature is enabled, raise 403 if not"""
    if not is_feature_enabled(feature_name):
        raise HTTPException(
            status_code=403,
            detail=f"Feature '{feature_name}' is disabled"
        )

# Video Info Endpoint
@router.get("/info", response_model=VideoInfoResponse)
async def get_video_info(
    url: str,
    ip: str = Depends(check_rate_limit),
    api_key: Optional[dict] = Depends(get_optional_api_key)
):
    """Get video information without downloading"""
    require_feature("video_info")
    
    with ErrorContext("get_video_info"):
        # Validate input
        url = InputValidator.validate_info_request(url)
        
        logger.info(f"Video info requested: {url[:60]}... from {ip}")
        
        try:
            info = await asyncio.wait_for(
                download_service.get_video_info(url),
                timeout=30
            )
            return VideoInfoResponse(**info)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting video info: {url[:60]}")
            raise HTTPException(status_code=408, detail="Request timeout")
        except ValueError as e:
            logger.warning(f"Invalid video info: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

# Download Endpoint
@router.post("/download", response_model=TaskResponse)
async def create_download(
    request: DownloadRequest,
    req: Request,
    ip: str = Depends(check_rate_limit),
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Create a new download task"""
    require_feature("download")
    
    with ErrorContext("create_download"):
        # Validate all input parameters
        url, format_type, quality = InputValidator.validate_download_request(
            str(request.url),
            request.format,
            request.quality,
            request.mp3_title
        )
        
        logger.info(f"Download task created: {url[:60]} format={format_type} from {ip}")
        
        try:
            task_id = await asyncio.wait_for(
                download_service.create_task(
                    url=url,
                    format_type=format_type,
                    format_id=request.format_id,
                    quality=quality,
                    ip_address=ip,
                    mp3_title=request.mp3_title,
                    embed_thumbnail=request.embed_thumbnail
                ),
                timeout=10
            )
            
            queue_pos = await redis_manager.get_queue_position(task_id)
            
            return TaskResponse(
                task_id=task_id,
                status="pending",
                queue_position=queue_pos,
                message="Task created and added to queue"
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout creating task for: {url[:60]}")
            raise HTTPException(status_code=408, detail="Task creation timeout")

# Status Endpoint
@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get task status via polling"""
    require_feature("status")
    
    with ErrorContext("get_task_status", task_id=task_id):
        # Validate task ID
        task_id = UUIDValidator.validate_or_raise(task_id)
        
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        if not task:
            raise TaskNotFoundError(task_id)
        
        return TaskStatusResponse(
            task_id=task.id,
            status=task.status,
            progress=task.progress,
            filename=task.filename,
            file_size=task.file_size,
            title=task.title,
            thumbnail_url=task.thumbnail_url,
            error_message=task.error_message,
            created_at=task.created_at,
            completed_at=task.completed_at
        )

# Download File Endpoint
@router.get("/download/{task_id}")
async def download_file(
    task_id: str,
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Download the completed file"""
    require_feature("file_download")
    
    with ErrorContext("download_file", task_id=task_id):
        # Validate task ID
        task_id = UUIDValidator.validate_or_raise(task_id)
        
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        if not task:
            raise TaskNotFoundError(task_id)
        
        if task.status != "completed":
            raise InvalidStateError(
                current_state=task.status,
                operation="download",
                allowed_states=["completed"]
            )
        
        if not task.file_path or not os.path.exists(task.file_path):
            logger.error(f"File not found for task: {task_id}")
            raise FileAccessError(task.file_path or "unknown", "File not found")
        
        # Security check: path traversal prevention
        file_path = Path(task.file_path).resolve()
        download_dir = Path(settings.DOWNLOAD_DIR).resolve()
        
        if not str(file_path).startswith(str(download_dir)):
            logger.error(f"Path traversal attempt detected: {task_id}")
            raise PathTraversalError(str(file_path))
        
        # Generate safe filename
        if task.title:
            safe_title = "".join(
                c for c in task.title if c.isalnum() or c in (' ', '-', '_')
            ).strip()
            if len(safe_title) > 200:
                safe_title = safe_title[:200]
            download_filename = f"{safe_title}{file_path.suffix}"
        else:
            download_filename = task.filename or f"{task_id}.mp4"
        
        logger.info(f"File download initiated: {task_id} as {download_filename}")
        
        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(file_path),
            filename=download_filename,
            media_type="application/octet-stream"
        )

# Cancel Task Endpoint
@router.post("/cancel/{task_id}")
async def cancel_task(
    task_id: str,
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Cancel a running download task"""
    require_feature("cancel")
    
    with ErrorContext("cancel_task", task_id=task_id):
        # Validate task ID
        task_id = UUIDValidator.validate_or_raise(task_id)
        
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        if not task:
            raise TaskNotFoundError(task_id)
        
        if task.status not in ["pending", "downloading"]:
            raise InvalidStateError(
                current_state=task.status,
                operation="cancel",
                allowed_states=["pending", "downloading"]
            )
        
        try:
            cancelled = await asyncio.wait_for(
                download_service.cancel_task(task_id),
                timeout=10
            )
            task.status = "cancelled"
            db.commit()
            logger.info(f"Task cancelled: {task_id}")
            return {"message": "Task cancelled", "cancelled": cancelled}
        except asyncio.TimeoutError:
            logger.warning(f"Timeout cancelling task: {task_id}")
            raise HTTPException(status_code=408, detail="Cancellation timeout")

# Delete Task Endpoint
@router.delete("/task/{task_id}")
async def delete_task(
    task_id: str,
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Delete a task and its file"""
    require_feature("delete")
    
    with ErrorContext("delete_task", task_id=task_id):
        # Validate task ID
        task_id = UUIDValidator.validate_or_raise(task_id)
        
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        if not task:
            raise TaskNotFoundError(task_id)
        
        # Delete file if exists
        if task.file_path:
            try:
                file_path = Path(task.file_path).resolve()
                download_dir = Path(settings.DOWNLOAD_DIR).resolve()
                
                # Security check
                if not str(file_path).startswith(str(download_dir)):
                    logger.warning(f"File path validation failed for deletion: {task_id}")
                    raise PathTraversalError(str(file_path))
                
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"File deleted for task: {task_id}")
            except Exception as e:
                logger.error(f"Failed to delete file for task {task_id}: {e}")
        
        try:
            db.delete(task)
            db.commit()
            logger.info(f"Task deleted: {task_id}")
            return {"message": "Task deleted"}
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete task")

# List Tasks Endpoint
@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """List all tasks (optionally filtered by status)"""
    require_feature("list_tasks")
    
    with ErrorContext("list_tasks"):
        query = db.query(DownloadTask)
        
        if status:
            valid_statuses = ["pending", "downloading", "completed", "failed", "cancelled"]
            if status not in valid_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {valid_statuses}"
                )
            query = query.filter(DownloadTask.status == status)
        
        try:
            tasks = query.order_by(DownloadTask.created_at.desc()).limit(limit).all()
            return [
                {
                    "task_id": task.id,
                    "url": task.url,
                    "status": task.status,
                    "progress": task.progress,
                    "title": task.title,
                    "format": task.format,
                    "created_at": task.created_at.isoformat()
                }
                for task in tasks
            ]
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve tasks")

# Get Thumbnail Endpoint
@router.get("/thumbnail/{task_id}")
async def get_thumbnail(
    task_id: str,
    api_key: Optional[dict] = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get thumbnail URL for a task"""
    require_feature("thumbnail")
    
    with ErrorContext("get_thumbnail", task_id=task_id):
        # Validate task ID
        task_id = UUIDValidator.validate_or_raise(task_id)
        
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        if not task:
            raise TaskNotFoundError(task_id)
        
        if not task.thumbnail_url:
            raise FileAccessError("unknown", "Thumbnail not available")
        
        return {"thumbnail_url": task.thumbnail_url}

# Download Subtitles Endpoint
@router.get("/subtitles")
async def get_subtitles(
    url: str,
    lang: str = Query("en"),
    ip: str = Depends(check_rate_limit),
    api_key: Optional[dict] = Depends(get_optional_api_key)
):
    """Download subtitles for a video"""
    require_feature("subtitles")
    
    with ErrorContext("get_subtitles"):
        # Validate input
        url, lang = InputValidator.validate_subtitle_request(url, lang)
        
        logger.info(f"Subtitles requested: {url[:60]} lang={lang} from {ip}")
        
        try:
            subtitles = await asyncio.wait_for(
                download_service.get_subtitles(url, lang),
                timeout=60
            )
            
            if not subtitles:
                raise FileAccessError(url, "Subtitles not found")
            
            return {
                "url": url,
                "language": lang,
                "subtitles": subtitles
            }
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting subtitles: {url[:60]}")
            raise HTTPException(status_code=408, detail="Subtitle download timeout")

# Queue Stats Endpoint
@router.get("/queue/stats")
async def get_queue_stats(
    api_key: Optional[dict] = Depends(get_optional_api_key)
):
    """Get queue statistics"""
    require_feature("queue_stats")
    
    with ErrorContext("get_queue_stats"):
        try:
            active = await redis_manager.get_active_downloads()
            pending_count = await redis_manager.get_queue_length()
            
            return {
                "active_downloads": len(active),
                "pending_tasks": pending_count,
                "max_concurrent": settings.MAX_CONCURRENT_DOWNLOADS,
                "available_slots": settings.MAX_CONCURRENT_DOWNLOADS - len(active),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            raise HTTPException(status_code=500, detail="Failed to get queue statistics")
