"""Pydantic models for request/response validation"""
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class DownloadRequest(BaseModel):
    """Download request model"""
    url: HttpUrl
    format: str = "mp4"  # mp3, mp4, best, audio, video, webm, wav, flac, aac
    format_id: Optional[str] = None  # Specific yt-dlp format ID
    quality: Optional[str] = None  # best, worst, or resolution like 1080p
    mp3_title: Optional[str] = None  # Custom title for MP3 files
    embed_thumbnail: bool = False  # Embed thumbnail in MP3

class TaskResponse(BaseModel):
    """Task creation response"""
    task_id: str
    status: str
    queue_position: int
    message: str

class TaskStatusResponse(BaseModel):
    """Task status response"""
    task_id: str
    status: str
    progress: float
    filename: Optional[str] = None
    file_size: Optional[int] = None
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class VideoFormat(BaseModel):
    """Video format information"""
    format_id: str
    resolution: str
    ext: str
    filesize: Optional[int] = None
    fps: Optional[float] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None

class VideoInfoResponse(BaseModel):
    """Video information response"""
    title: str
    thumbnail: Optional[str] = None
    duration: int
    view_count: int
    like_count: int
    uploader: str
    upload_date: Optional[str] = None
    formats: List[VideoFormat]
    available_qualities: List[str]
    available_audio_formats: List[str]
