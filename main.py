from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Union
import asyncio
from datetime import datetime

from config import settings
from database import init_db, get_db, DownloadTask
from redis_manager import redis_manager
from download_service import download_service
from queue_worker import queue_worker
from rate_limiter import check_rate_limit
from websocket_manager import ws_manager

app = FastAPI(
    title="yt-dlp Download API",
    description="Full-featured video/audio download API with queue management",
    version="1.0.0"
)

# CORS
origins = settings.CORS_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
    init_db()
    await redis_manager.connect()
    asyncio.create_task(queue_worker.start())
    print("✅ yt-dlp API started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await queue_worker.stop()
    await redis_manager.disconnect()
    print("👋 yt-dlp API shutdown")

# Health check
@app.get("/")
async def root():
    return {
        "service": "yt-dlp Download API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Video info endpoint
@app.get("/api/info", response_model=VideoInfoResponse)
async def get_video_info(
    url: str,
    ip: str = Depends(check_rate_limit)
):
    """Get video information without downloading"""
    try:
        info = await download_service.get_video_info(url)
        return VideoInfoResponse(**info)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        
        return TaskResponse(
            task_id=task_id,
            status="pending",
            queue_position=queue_pos,
            message="Task created and added to queue"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Status endpoint (polling)
@app.get("/api/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    db = Depends(get_db)
):
    """Get task status via polling"""
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    
    if not task:
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
    
    try:
        db = next(get_db())
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        
        if not task:
            await websocket.send_json({"error": "Task not found"})
            await websocket.close()
            return
        
        # Send initial status
        await websocket.send_json({
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress
        })
        
        # Keep connection alive and send updates
        while True:
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
        
        db.close()
        
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, task_id)

# Download file endpoint
@app.get("/api/download/{task_id}")
async def download_file(
    task_id: str,
    db = Depends(get_db)
):
    """Download the completed file"""
    import os
    from pathlib import Path
    
    task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")
    
    if not task.file_path or not os.path.exists(task.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
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
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["pending", "downloading"]:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")
    
    # Cancel process if running
    cancelled = await download_service.cancel_task(task_id)
    
    # Update status
    task.status = "cancelled"
    db.commit()
    
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
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete file if exists
    if task.file_path:
        try:
            import os
            if os.path.exists(task.file_path):
                os.remove(task.file_path)
        except Exception as e:
            print(f"Failed to delete file: {e}")
    
    # Delete from database
    db.delete(task)
    db.commit()
    
    return {"message": "Task deleted"}

# List tasks
@app.get("/api/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    db = Depends(get_db)
):
    """List all tasks (optionally filtered by status)"""
    query = db.query(DownloadTask)
    
    if status:
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
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.thumbnail_url:
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
        subtitles = await download_service.get_subtitles(url, lang)
        
        if not subtitles:
            raise HTTPException(status_code=404, detail="Subtitles not found")
        
        return {
            "url": url,
            "language": lang,
            "subtitles": subtitles
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Queue stats
@app.get("/api/queue/stats")
async def get_queue_stats():
    """Get queue statistics"""
    active = await redis_manager.get_active_downloads()
    
    return {
        "active_downloads": len(active),
        "max_concurrent": settings.MAX_CONCURRENT_DOWNLOADS,
        "available_slots": settings.MAX_CONCURRENT_DOWNLOADS - len(active)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)