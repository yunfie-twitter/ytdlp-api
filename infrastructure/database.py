"""Database initialization and models"""
import logging
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class DownloadTask(Base):
    """Download task model"""
    __tablename__ = "download_tasks"
    
    id = Column(String, primary_key=True, index=True)
    url = Column(String, index=True)
    format = Column(String)
    format_id = Column(String, nullable=True)
    quality = Column(String, nullable=True)
    status = Column(String, default="pending", index=True)
    progress = Column(Float, default=0.0)
    ip_address = Column(String, nullable=True)
    
    # File information
    filename = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    
    # Video metadata
    title = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    
    # Audio metadata
    mp3_title = Column(String, nullable=True)
    embed_thumbnail = Column(Boolean, default=False)
    
    # Process information
    process_id = Column(Integer, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def get_db():
    """Get database session generator"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
