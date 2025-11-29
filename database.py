from sqlalchemy import create_engine, Column, String, Integer, DateTime, Float, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DownloadTask(Base):
    __tablename__ = "download_tasks"
    
    id = Column(String, primary_key=True, index=True)
    url = Column(String, nullable=False)
    format = Column(String, nullable=False)
    format_id = Column(String, nullable=True)  # yt-dlpの特定フォーマットID
    quality = Column(String, nullable=True)  # 画質指定 (1080p, 720p, best, worst等)
    status = Column(String, default="pending")  # pending, downloading, completed, failed, cancelled
    progress = Column(Float, default=0.0)
    file_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    filename = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    
    # Video info
    title = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    
    # MP3 tag options
    mp3_title = Column(String, nullable=True)
    embed_thumbnail = Column(Boolean, default=False)
    
    # Metadata
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Process info
    process_id = Column(Integer, nullable=True)
    
def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()