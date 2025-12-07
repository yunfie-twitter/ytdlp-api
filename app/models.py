"""Pydantic models for API requests/responses"""
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Union
from datetime import datetime


class DownloadRequest(BaseModel):
    """Request model for creating a download task"""
    url: HttpUrl
    format: str = "mp4"  # mp3, mp4, best, audio, video, webm, wav, flac, aac
    format_id: Optional[str] = None  # yt-dlpの特定フォーマットID (例: "137+140")
    quality: Optional[str] = None  # 画質指定 (例: "1080p", "720p", "best", "worst")
    mp3_title: Optional[str] = None
    embed_thumbnail: bool = False


class TaskResponse(BaseModel):
    """Response model for task creation"""
    task_id: str
    status: str
    queue_position: Optional[int] = None
    message: str


class TaskStatusResponse(BaseModel):
    """Response model for task status"""
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
    """Video format option"""
    format_id: str
    resolution: str
    ext: str
    filesize: Optional[int] = None
    fps: Optional[Union[int, float]] = None  # intまたはfloatを受け入れる
    vcodec: Optional[str] = None
    acodec: Optional[str] = None


class VideoInfoResponse(BaseModel):
    """Response model for video information"""
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
