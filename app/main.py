"""Main FastAPI application factory"""
import asyncio
import logging
import os
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from core.config import settings
from core.security import check_rate_limit, set_redis_manager
from app.models import (
    DownloadRequest, TaskResponse, TaskStatusResponse,
    VideoInfoResponse
)
from infrastructure.database import init_db, get_db, DownloadTask
from infrastructure.redis_manager import redis_manager
from infrastructure.websocket_manager import ws_manager
from services.download_service import download_service
from services.queue_worker import queue_worker

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    app = FastAPI(
        title="yt-dlp Download API",
        description="Full-featured video/audio download API with queue management",
        version="1.0.3",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json"
    )
    
    # CORS - More secure configuration
    allowed_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
    if "*" not in allowed_origins:
        # Specific origins for production
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
            max_age=3600,
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
            max_age=3600,
        )
    
    # Startup/Shutdown
    @app.on_event("startup")
    async def startup_event():
        """Initialize services"""
        try:
            logger.info("Starting up yt-dlp API...")
            init_db()
            logger.info("✓ Database initialized")
            await redis_manager.connect()
            logger.info("✓ Redis connected")
            set_redis_manager(redis_manager)
            asyncio.create_task(queue_worker.start())
            logger.info("✓ Queue worker started")
            logger.info("✅ yt-dlp API started successfully")
        except Exception as e:
            logger.error(f"❌ Failed to start API: {e}", exc_info=True)
            raise
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown"""
        try:
            logger.info("Shutting down yt-dlp API...")
            await queue_worker.stop()
            logger.info("✓ Queue worker stopped")
            await redis_manager.disconnect()
            logger.info("✓ Redis disconnected")
            logger.info("👋 yt-dlp API shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    # Health check
    @app.get("/")
    async def root():
        return {
            "service": "yt-dlp Download API",
            "version": "1.0.3",
            "status": "running"
        }
    
    @app.get("/health")
    async def health_check():
        try:
            redis_ok = await redis_manager.ping()
            return {
                "status": "healthy" if redis_ok else "degraded",
                "redis": "connected" if redis_ok else "disconnected",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.warning(f"Health check warning: {e}")
            return {"status": "degraded", "message": str(e), "timestamp": datetime.utcnow().isoformat()}, 503
    
    # Video info endpoint
    @app.get("/api/info", response_model=VideoInfoResponse)
    async def get_video_info(
        url: str,
        ip: str = Depends(check_rate_limit)
    ):
        """Get video information without downloading"""
        if not url or not _is_valid_url(url):
            logger.warning(f"Invalid URL format from {ip}: {url[:50] if url else 'None'}")
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        try:
            logger.info(f"Getting video info for: {url[:60]}... from {ip}")
            info = await download_service.get_video_info(url)
            return VideoInfoResponse(**info)
        except ValueError as e:
            logger.warning(f"Invalid video info request: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting video info for: {url[:60]}...")
            raise HTTPException(status_code=408, detail="Request timeout")
        except Exception as e:
            logger.error(f"Failed to get video info for {url[:60]}...: {e}", exc_info=True)
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
        if not _is_valid_url(str(request.url)):
            logger.warning(f"Invalid URL format from {ip}: {str(request.url)[:50]}")
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        # Validate format
        valid_formats = ["mp3", "mp4", "best", "audio", "video", "webm", "wav", "flac", "aac"]
        if request.format.lower() not in valid_formats:
            logger.warning(f"Invalid format requested from {ip}: {request.format}")
            raise HTTPException(status_code=400, detail=f"Invalid format. Must be one of: {valid_formats}")
        
        try:
            logger.info(f"Creating download task for: {str(request.url)[:60]}... format: {request.format} from {ip}")
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
        if not _is_valid_uuid(task_id):
            logger.warning(f"Invalid task ID format: {task_id}")
            raise HTTPException(status_code=400, detail="Invalid task ID format")
        
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
        if not _is_valid_uuid(task_id):
            logger.warning(f"WebSocket: Invalid task ID format: {task_id}")
            await websocket.close(code=1008, reason="Invalid task ID format")
            return
        
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
            
            await websocket.send_json({
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress
            })
            
            while True:
                try:
                    db.refresh(task)
                    
                    await websocket.send_json({
                        "task_id": task.id,
                        "status": task.status,
                        "progress": task.progress,
                        "filename": task.filename
                    })
                    
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
        if not _is_valid_uuid(task_id):
            logger.warning(f"Invalid task ID format: {task_id}")
            raise HTTPException(status_code=400, detail="Invalid task ID format")
        
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
        
        file_path = Path(task.file_path).resolve()
        download_dir = Path(settings.DOWNLOAD_DIR).resolve()
        
        if not str(file_path).startswith(str(download_dir)):
            logger.error(f"Download: Path traversal attempt detected for task: {task_id}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        if task.title:
            safe_title = "".join(c for c in task.title if c.isalnum() or c in (' ', '-', '_')).strip()
            if len(safe_title) > 200:
                safe_title = safe_title[:200]
            
            original_ext = Path(task.file_path).suffix
            download_filename = f"{safe_title}{original_ext}"
        else:
            download_filename = task.filename or f"{task_id}.mp4"
        
        logger.info(f"Downloading file for task: {task_id} as {download_filename}")
        
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
        if not _is_valid_uuid(task_id):
            logger.warning(f"Invalid task ID format: {task_id}")
            raise HTTPException(status_code=400, detail="Invalid task ID format")
        
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        
        if not task:
            logger.warning(f"Cancel: Task not found: {task_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.status not in ["pending", "downloading"]:
            logger.warning(f"Cancel: Task cannot be cancelled: {task_id} (status: {task.status})")
            raise HTTPException(status_code=400, detail="Task cannot be cancelled")
        
        try:
            cancelled = await download_service.cancel_task(task_id)
            task.status = "cancelled"
            db.commit()
            logger.info(f"Task cancelled: {task_id}")
            return {"message": "Task cancelled", "cancelled": cancelled}
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to cancel task")
    
    # Delete task
    @app.delete("/api/task/{task_id}")
    async def delete_task(
        task_id: str,
        db = Depends(get_db)
    ):
        """Delete a task and its file"""
        if not _is_valid_uuid(task_id):
            logger.warning(f"Invalid task ID format: {task_id}")
            raise HTTPException(status_code=400, detail="Invalid task ID format")
        
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        
        if not task:
            logger.warning(f"Delete: Task not found: {task_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.file_path:
            try:
                file_path = Path(task.file_path).resolve()
                download_dir = Path(settings.DOWNLOAD_DIR).resolve()
                
                if str(file_path).startswith(str(download_dir)) and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted file for task: {task_id}")
            except Exception as e:
                logger.error(f"Failed to delete file for task {task_id}: {e}", exc_info=True)
        
        try:
            db.delete(task)
            db.commit()
            logger.info(f"Task deleted: {task_id}")
            return {"message": "Task deleted"}
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete task")
    
    # List tasks
    @app.get("/api/tasks")
    async def list_tasks(
        status: Optional[str] = None,
        limit: int = 50,
        db = Depends(get_db)
    ):
        """List all tasks (optionally filtered by status)"""
        if limit > 200:
            limit = 200
        elif limit < 1:
            limit = 1
        
        query = db.query(DownloadTask)
        
        if status:
            valid_statuses = ["pending", "downloading", "completed", "failed", "cancelled"]
            if status not in valid_statuses:
                logger.warning(f"Invalid status filter: {status}")
                raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
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
            logger.error(f"Error listing tasks: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to retrieve tasks")
    
    # Get thumbnail
    @app.get("/api/thumbnail/{task_id}")
    async def get_thumbnail(
        task_id: str,
        db = Depends(get_db)
    ):
        """Get thumbnail URL for a task"""
        if not _is_valid_uuid(task_id):
            logger.warning(f"Invalid task ID format: {task_id}")
            raise HTTPException(status_code=400, detail="Invalid task ID format")
        
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
        if not url or not _is_valid_url(url):
            logger.warning(f"Invalid URL format from {ip}: {url[:50] if url else 'None'}")
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        if not _is_valid_language_code(lang):
            logger.warning(f"Invalid language code from {ip}: {lang}")
            raise HTTPException(status_code=400, detail="Invalid language code format")
        
        try:
            logger.info(f"Getting subtitles for: {url[:60]}... (lang: {lang}) from {ip}")
            subtitles = await download_service.get_subtitles(url, lang)
            
            if not subtitles:
                logger.warning(f"Subtitles not found: {url[:60]}... (lang: {lang})")
                raise HTTPException(status_code=404, detail="Subtitles not found")
            
            return {
                "url": url,
                "language": lang,
                "subtitles": subtitles
            }
        except ValueError as e:
            logger.warning(f"Invalid subtitles request: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting subtitles for: {url[:60]}...")
            raise HTTPException(status_code=408, detail="Request timeout")
        except Exception as e:
            logger.error(f"Failed to get subtitles: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail="Failed to retrieve subtitles")
    
    # Queue stats
    @app.get("/api/queue/stats")
    async def get_queue_stats():
        """Get queue statistics"""
        try:
            active = await redis_manager.get_active_downloads()
            pending_count = await redis_manager.get_queue_length()
            
            return {
                "active_downloads": len(active),
                "pending_tasks": pending_count,
                "max_concurrent": settings.MAX_CONCURRENT_DOWNLOADS,
                "available_slots": settings.MAX_CONCURRENT_DOWNLOADS - len(active)
            }
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to retrieve queue statistics")
    
    return app

def _is_valid_url(url: str) -> bool:
    """Validate URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False

def _is_valid_uuid(uuid_str: str) -> bool:
    """Validate UUID format"""
    try:
        import uuid
        uuid.UUID(uuid_str)
        return True
    except (ValueError, AttributeError):
        return False

def _is_valid_language_code(lang: str) -> bool:
    """Validate language code format (e.g., en, ja, en-US)"""
    import re
    return bool(re.match(r'^[a-z]{2}(-[A-Z]{2})?$', lang))

app = create_app()
