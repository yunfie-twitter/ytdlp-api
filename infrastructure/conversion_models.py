"""Database models for conversion tasks"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship
import enum

from infrastructure.database import Base


class ConversionStatus(str, enum.Enum):
    """Conversion task status"""
    PENDING = "pending"
    QUEUED = "queued"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConversionTask(Base):
    """Model for video/audio conversion tasks"""
    __tablename__ = "conversion_tasks"
    
    id = Column(String(36), primary_key=True)
    # Source file reference
    source_file_path = Column(String(512), nullable=False, index=True)
    source_format = Column(String(10), nullable=False)  # e.g., 'mp4', 'webm', 'm4a'
    source_bitrate = Column(String(20))  # e.g., '128k', '5M'
    source_duration = Column(Float)  # Duration in seconds
    
    # Target format
    target_format = Column(String(10), nullable=False, index=True)  # e.g., 'mp4', 'mp3', 'wav'
    target_bitrate = Column(String(20))  # Optional: for audio
    target_codec = Column(String(20))  # Optional: e.g., 'libmp3lame', 'aac'
    sample_rate = Column(Integer)  # Optional: for audio (e.g., 44100, 48000)
    
    # Audio-specific settings
    audio_only = Column(Boolean, default=False)  # Convert to audio only
    channels = Column(Integer)  # 1=mono, 2=stereo, etc.
    
    # Processing
    status = Column(Enum(ConversionStatus), default=ConversionStatus.PENDING, index=True)
    progress = Column(Float, default=0.0)  # 0-100
    output_file_path = Column(String(512))
    output_file_size = Column(Integer)  # Bytes
    output_filename = Column(String(256))
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    title = Column(String(256))  # Original title
    priority = Column(Integer, default=0)  # Higher = more important
    ip_address = Column(String(45))  # IPv4 or IPv6
    process_id = Column(Integer)  # PID of conversion process
    
    # Performance tracking
    encoding_speed = Column(Float)  # Speed relative to real-time (e.g., 2.5x)
    
    def __repr__(self):
        return f"<ConversionTask {self.id} {self.source_format}->{self.target_format} {self.status.value}>"
