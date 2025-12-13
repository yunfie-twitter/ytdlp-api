"""API endpoints for media conversion tasks"""
import logging
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request

from services.conversion_service import conversion_service
from services.conversion_queue import conversion_queue
from infrastructure.database import get_db, ConversionTask
from infrastructure.conversion_models import ConversionStatus
from core.validation.conversion_validation import conversion_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversion", tags=["conversion"])


class CreateConversionTaskRequest(BaseModel):
    """Request model for creating conversion task"""
    source_file_path: str = Field(..., description="Path to source file (from download)")
    source_format: str = Field(..., description="Source file format (e.g., 'mp4', 'webm', 'm4a')")
    target_format: str = Field(..., description="Target format (e.g., 'mp3', 'wav', 'flac')")
    target_bitrate: Optional[str] = Field(None, description="Target bitrate (e.g., '192k', '5M')")
    target_codec: Optional[str] = Field(None, description="Target codec (e.g., 'libmp3lame', 'aac')")
    sample_rate: Optional[int] = Field(None, description="Sample rate in Hz (e.g., 44100, 48000)")
    channels: Optional[int] = Field(None, description="Number of channels (1=mono, 2=stereo)")
    audio_only: bool = Field(False, description="Convert to audio only (extract audio from video)")
    title: Optional[str] = Field(None, description="Task title/name")
    priority: int = Field(0, description="Priority level (higher = more important)")
    max_retries: int = Field(3, description="Maximum retry attempts on failure")


class ConversionTaskResponse(BaseModel):
    """Response model for conversion task"""
    task_id: str
    status: str
    progress: float
    source_format: str
    target_format: str
    source_file_path: str
    output_file_path: Optional[str]
    output_filename: Optional[str]
    output_file_size: Optional[int]
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    encoding_speed: Optional[float]


class ConversionQueueStatsResponse(BaseModel):
    """Response model for queue statistics"""
    queued: int
    active: int
    completed: int
    failed: int
    cancelled: int
    retried: int


@router.post("/tasks", response_model=dict)
async def create_conversion_task(
    request_data: CreateConversionTaskRequest,
    request: Request
):
    """Create a new conversion task
    
    This endpoint creates a conversion task for transforming media files
    from one format to another using ffmpeg.
    
    Supported audio formats: mp3, wav, flac, aac, opus, vorbis, m4a, ogg, alac
    Supported video formats: mp4, webm, mkv, mov, avi, flv, hdr, h265
    """
    try:
        # Get client IP
        ip_address = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or request.client.host
        )
        
        # Validate format
        if not conversion_validator.validate_format(request_data.target_format):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported target format: {request_data.target_format}"
            )
        
        # Validate parameters
        is_valid, error_msg = conversion_validator.validate_conversion_params(
            request_data.source_format,
            request_data.target_format,
            request_data.target_bitrate,
            request_data.sample_rate,
            request_data.channels
        )
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Create task
        task_id = await conversion_service.create_task(
            source_file_path=request_data.source_file_path,
            source_format=request_data.source_format,
            target_format=request_data.target_format,
            ip_address=ip_address,
            target_bitrate=request_data.target_bitrate,
            target_codec=request_data.target_codec,
            sample_rate=request_data.sample_rate,
            channels=request_data.channels,
            audio_only=request_data.audio_only,
            title=request_data.title,
            priority=request_data.priority,
            max_retries=request_data.max_retries
        )
        
        # Add to queue
        success = await conversion_queue.enqueue(
            task_id=task_id,
            priority=request_data.priority,
            max_retries=request_data.max_retries,
            timeout=14400  # 4 hours
        )
        
        if not success:
            logger.error(f"Failed to enqueue conversion task {task_id}")
            raise HTTPException(
                status_code=500,
                detail="Failed to enqueue conversion task"
            )
        
        return {
            "task_id": task_id,
            "status": "pending",
            "message": f"Conversion task created and queued for {request_data.source_format} → {request_data.target_format}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversion task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}", response_model=ConversionTaskResponse)
async def get_conversion_task(task_id: str):
    """Get conversion task details"""
    db = next(get_db())
    try:
        task = db.query(ConversionTask).filter(ConversionTask.id == task_id).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="Conversion task not found")
        
        return ConversionTaskResponse(
            task_id=task.id,
            status=task.status.value if isinstance(task.status, ConversionStatus) else task.status,
            progress=task.progress,
            source_format=task.source_format,
            target_format=task.target_format,
            source_file_path=task.source_file_path,
            output_file_path=task.output_file_path,
            output_filename=task.output_filename,
            output_file_size=task.output_file_size,
            error_message=task.error_message,
            created_at=task.created_at.isoformat() if task.created_at else None,
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            encoding_speed=task.encoding_speed
        )
    finally:
        db.close()


@router.post("/tasks/{task_id}/cancel", response_model=dict)
async def cancel_conversion_task(task_id: str):
    """Cancel a conversion task"""
    db = next(get_db())
    try:
        task = db.query(ConversionTask).filter(ConversionTask.id == task_id).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="Conversion task not found")
        
        if task.status == ConversionStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel a completed task"
            )
        
        # Try to cancel the process
        cancelled = await conversion_service.cancel_task(task_id)
        
        # Mark as cancelled in DB
        task.status = ConversionStatus.CANCELLED
        db.commit()
        
        # Mark in queue
        await conversion_queue.mark_cancelled(task_id)
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": f"Conversion task {task_id} has been cancelled"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling conversion task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/queue/stats", response_model=ConversionQueueStatsResponse)
async def get_queue_stats():
    """Get conversion queue statistics"""
    try:
        stats = await conversion_queue.get_stats()
        return ConversionQueueStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get queue statistics")


@router.get("/formats")
async def get_supported_formats():
    """Get list of supported conversion formats"""
    from core.validation.conversion_validation import AUDIO_FORMATS, VIDEO_FORMATS
    
    return {
        "audio_formats": {
            name: {
                "codec": info.get("codec"),
                "default_bitrate": info.get("default_bitrate"),
                "lossless": info.get("lossless", False),
                "sample_rates": info.get("sample_rates", []),
            }
            for name, info in AUDIO_FORMATS.items()
        },
        "video_formats": {
            name: {
                "codec": info.get("codec"),
                "hw_encoders": info.get("hw_encoders", [])
            }
            for name, info in VIDEO_FORMATS.items()
        }
    }


@router.get("/formats/{format_name}")
async def get_format_info(format_name: str):
    """Get detailed information about a specific format"""
    try:
        info = conversion_validator.get_format_info(format_name)
        return {
            "format": format_name,
            "info": info,
            "is_audio": conversion_validator.is_audio_format(format_name),
            "is_video": conversion_validator.is_video_format(format_name)
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
