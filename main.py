from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Union
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from config import settings
from database import init_db, get_db, DownloadTask
from redis_manager import redis_manager
from download_service import download_service
from queue_worker import queue_worker
from rate_limiter import check_rate_limit
from websocket_manager import ws_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="yt-dlp Download API",
    description="Full-featured video/audio download API with queue management",
    version="1.0.1"
)

# CORS - More secure configuration
allowed_origins = settings.CORS_ORIGINS.split(",")
if "*" not in allowed_origins:
    # Specific origins for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
else:
    # Allow all for development (log warning)
    logger.warning("⚠️  CORS is set to allow all origins. This is NOT recommended for production!")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Models
class DownloadRequest(BaseModel):
    url: HttpUrl
    format: str = "mp4"  # mp3, mp4, best, audio, video, webm, wav, flac, aac
    format_id: Optional[str] = None  # yt-dlpの特定フォーマットID (例: "137+140")
    quality: Optional[str] = None  # 画質指定 (例: "1080p", "720p", "best", "worst")
    mp3_title: Optional[str] = None
    embed_thumbnail: bool = False

class TaskResponse(BaseModel):
    task_id: str
    status: str
    queue_position: Optional[int] = None
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    filename: Optional[str] = None
    file_size: Optional[int] = None
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class FormatOption(BaseModel):
    format_id: str
    resolution: str
    ext: str
    filesize: Optional[int] = None
    fps: Optional[Union[int, float]] = None  # intまたはfloatを受け入れる
    vcodec: Optional[str] = None
    acodec: Optional[str] = None

class VideoInfoResponse(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: int
    view_count: int
    like_count: int
    uploader: str
    upload_date: Optional[str] = None
    formats: List[FormatOption]
    available_qualities: List[str]  # 利用可能な画質一覧
    available_audio_formats: List[str]  # 利用可能な音声フォーマット一覧

# Startup/Shutdown
@app.on_event("startup")
async def startup_event():
    """Initialize services"""
    try:
        init_db()
        await redis_manager.connect()
        asyncio.create_task(queue_worker.start())
        logger.info("✅ yt-dlp API started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start API: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        await queue_worker.stop()
        await redis_manager.disconnect()
        logger.info("👋 yt-dlp API shutdown")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

# Health check
@app.get("/")
async def root():
    return {
        "service": "yt-dlp Download API",
        "version": "1.0.1",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    try:
        # Check Redis connection
        await redis_manager.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        logger.warning(f"Health check warning: {e}")
        return {"status": "degraded", "message": str(e)}, 503

# Video info endpoint
@app.get("/api/info", response_model=VideoInfoResponse)
async def get_video_info(
    url: str,
    ip: str = Depends(check_rate_limit)
):
    """Get video information without downloading"""
    try:
        logger.info(f"Getting video info for: {url[:50]}...")
        info = await download_service.get_video_info(url)
        return VideoInfoResponse(**info)
    except ValueError as e:
        logger.warning(f"Invalid video info request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get video info: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to retrieve video information")

# Download endpoint
@app.post("/api/download", response_model=TaskResponse)
async def create_download(
    request: DownloadRequest,
    req: Request,
    ip: str = Depends(check_rate_limit),
    db = Depends(get_db)
):
    """Create a new download task"""
    try:
        logger.info(f"Creating download task for: {str(request.url)[:50]}... from {ip}")
        task_id = await download_service.create_task(
            url=str(request.url),
            format_type=request.format,
            format_id=request.format_id,
            quality=request.quality,
            ip_address=ip,
            mp3_title=request.mp3_title,
            embed_thumbnail=request.embed_thumbnail
        )
        
        queue_pos = await redis_manager.get_queue_position(task_id)
        
        logger.info(f"Task created: {task_id}, position: {queue_pos}")
        return TaskResponse(
            task_id=task_id,
            status="pending",
            queue_position=queue_pos,
            message="Task created and added to queue"
        )
    except ValueError as e:
        logger.warning(f"Invalid download request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create download task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create download task")

# Status endpoint (polling)
@app.get("/api/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    db = Depends(get_db)
):
    """Get task status via polling"""
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
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

# WebSocket endpoint (real-time progress)
@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket for real-time progress updates"""
    await ws_manager.connect(websocket, task_id)
    
    db = None
    try:
        db = next(get_db())
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        
        if not task:
            logger.warning(f"WebSocket: Task not found: {task_id}")
            await websocket.send_json({"error": "Task not found"})
            await websocket.close(code=1008, reason="Task not found")
            return
        
        # Send initial status
        await websocket.send_json({
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress
        })
        
        # Keep connection alive and send updates
        while True:
            try:
                # Check task status every second
                db.refresh(task)
                
                await websocket.send_json({
                    "task_id": task.id,
                    "status": task.status,
                    "progress": task.progress,
                    "filename": task.filename
                })
                
                # Close if completed/failed
                if task.status in ["completed", "failed", "cancelled"]:
                    break
                
                await asyncio.sleep(1)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for task: {task_id}")
                break
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task: {task_id}")
        ws_manager.disconnect(websocket, task_id)
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}", exc_info=True)
        ws_manager.disconnect(websocket, task_id)
    finally:
        if db:
            db.close()

# Download file endpoint
@app.get("/api/download/{task_id}")
async def download_file(
    task_id: str,
    db = Depends(get_db)
):
    """Download the completed file"""
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    
    if not task:
        logger.warning(f"Download: Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "completed":
        logger.warning(f"Download: Task not completed: {task_id} (status: {task.status})")
        raise HTTPException(status_code=400, detail="Task not completed yet")
    
    if not task.file_path or not os.path.exists(task.file_path):
        logger.error(f"Download: File not found for task: {task_id}")
        raise HTTPException(status_code=404, detail="File not found")
    
    # Verify file path is within download directory (security)
    file_path = Path(task.file_path).resolve()
    download_dir = Path(settings.DOWNLOAD_DIR).resolve()
    
    if not str(file_path).startswith(str(download_dir)):
        logger.error(f"Download: Path traversal attempt detected for task: {task_id}")
        raise HTTPException(status_code=403, detail="Access denied")
    
    # タイトルベースのファイル名を生成
    if task.title:
        # ファイル名として使用できない文字を削除
        safe_title = "".join(c for c in task.title if c.isalnum() or c in (' ', '-', '_')).strip()
        # 長すぎる場合は切り詰め
        if len(safe_title) > 200:
            safe_title = safe_title[:200]
        
        # 拡張子を取得
        original_ext = Path(task.file_path).suffix
        download_filename = f"{safe_title}{original_ext}"
    else:
        # タイトルがない場合は元のファイル名を使用
        download_filename = task.filename or f"{task_id}.mp4"
    
    logger.info(f"Downloading file for task: {task_id}")
    
    return FileResponse(
        path=task.file_path,
        filename=download_filename,
        media_type="application/octet-stream"
    )

# Cancel task
@app.post("/api/cancel/{task_id}")
async def cancel_task(
    task_id: str,
    db = Depends(get_db)
):
    """Cancel a running download task"""
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    
    if not task:
        logger.warning(f"Cancel: Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["pending", "downloading"]:
        logger.warning(f"Cancel: Task cannot be cancelled: {task_id} (status: {task.status})")
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")
    
    # Cancel process if running
    cancelled = await download_service.cancel_task(task_id)
    
    # Update status
    task.status = "cancelled"
    db.commit()
    
    logger.info(f"Task cancelled: {task_id}")
    
    return {"message": "Task cancelled", "cancelled": cancelled}

# Delete task
@app.delete("/api/task/{task_id}")
async def delete_task(
    task_id: str,
    db = Depends(get_db)
):
    """Delete a task and its file"""
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    
    if not task:
        logger.warning(f"Delete: Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete file if exists
    if task.file_path:
        try:
            file_path = Path(task.file_path).resolve()
            download_dir = Path(settings.DOWNLOAD_DIR).resolve()
            
            # Verify file path is within download directory (security)
            if str(file_path).startswith(str(download_dir)) and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file for task: {task_id}")
        except Exception as e:
            logger.error(f"Failed to delete file for task {task_id}: {e}")
    
    # Delete from database
    db.delete(task)
    db.commit()
    
    logger.info(f"Task deleted: {task_id}")
    
    return {"message": "Task deleted"}

# List tasks
@app.get("/api/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    db = Depends(get_db)
):
    """List all tasks (optionally filtered by status)"""
    if limit > 200:
        limit = 200  # Cap the limit for performance
    
    query = db.query(DownloadTask)
    
    if status:
        # Validate status
        valid_statuses = ["pending", "downloading", "completed", "failed", "cancelled"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        query = query.filter(DownloadTask.status == status)
    
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

# Get thumbnail
@app.get("/api/thumbnail/{task_id}")
async def get_thumbnail(
    task_id: str,
    db = Depends(get_db)
):
    """Get thumbnail URL for a task"""
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    
    if not task:
        logger.warning(f"Thumbnail: Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.thumbnail_url:
        logger.warning(f"Thumbnail: Not available for task: {task_id}")
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    
    return {"thumbnail_url": task.thumbnail_url}

# Download subtitles
@app.get("/api/subtitles")
async def get_subtitles(
    url: str,
    lang: str = "en",
    ip: str = Depends(check_rate_limit)
):
    """Download subtitles for a video"""
    try:
        logger.info(f"Getting subtitles for: {url[:50]}... (lang: {lang})")
        subtitles = await download_service.get_subtitles(url, lang)
        
        if not subtitles:
            logger.warning(f"Subtitles not found: {url[:50]}... (lang: {lang})")
            raise HTTPException(status_code=404, detail="Subtitles not found")
        
        return {
            "url": url,
            "language": lang,
            "subtitles": subtitles
        }
    except ValueError as e:
        logger.warning(f"Invalid subtitles request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get subtitles: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to retrieve subtitles")

# Queue stats
@app.get("/api/queue/stats")
async def get_queue_stats():
    """Get queue statistics"""
    try:
        active = await redis_manager.get_active_downloads()
        
        return {
            "active_downloads": len(active),
            "max_concurrent": settings.MAX_CONCURRENT_DOWNLOADS,
            "available_slots": settings.MAX_CONCURRENT_DOWNLOADS - len(active)
        }
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve queue statistics")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)