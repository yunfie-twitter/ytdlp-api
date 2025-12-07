"""Configuration management using Pydantic Settings"""
from pydantic_settings import BaseSettings
from typing import Optional
from datetime import timedelta

class Settings(BaseSettings):
    """Application settings with JWT and feature flags"""
    
    # ==================== API Settings ====================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False
    
    # ==================== CORS ====================
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    # ==================== Database ====================
    DATABASE_URL: str = "sqlite:///./download_tasks.db"
    
    # ==================== Redis ====================
    REDIS_URL: str = "redis://localhost:6379"
    
    # ==================== Download Settings ====================
    DOWNLOAD_DIR: str = "./downloads"
    MAX_CONCURRENT_DOWNLOADS: int = 3
    AUTO_DELETE_AFTER: int = 604800  # 7 days
    
    # ==================== GPU Encoding ====================
    ENABLE_GPU_ENCODING: bool = False
    GPU_ENCODER_TYPE: str = "auto"  # auto, nvenc, vaapi, qsv
    GPU_ENCODER_PRESET: str = "fast"  # fast, medium, slow
    
    # ==================== Aria2 ====================
    ENABLE_ARIA2: bool = False
    ARIA2_MAX_CONNECTIONS: int = 4
    ARIA2_SPLIT: int = 4
    
    # ==================== Deno/JavaScript Runtime ====================
    ENABLE_DENO: bool = False
    DENO_PATH: str = "/usr/local/bin/deno"
    
    # ==================== yt-dlp Settings ====================
    YTDLP_PROXY: Optional[str] = None
    YTDLP_COOKIES_FILE: Optional[str] = None
    
    # ==================== Rate Limiting ====================
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # ==================== Security ====================
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # ==================== JWT Authentication ====================
    # Enable/Disable JWT authentication system
    ENABLE_JWT_AUTH: bool = False
    
    # Password required to issue new API keys
    # If not set, API key issuance is disabled
    API_KEY_ISSUE_PASSWORD: Optional[str] = None
    
    # JWT configuration
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 30
    
    # Redis key prefix for API keys
    REDIS_API_KEY_PREFIX: str = "api_key:"
    
    # Whether to validate API key on every request
    JWT_VALIDATE_ON_EVERY_REQUEST: bool = True
    
    # ==================== Feature Flags ====================
    # Video Info endpoint
    ENABLE_FEATURE_VIDEO_INFO: bool = True
    
    # Download endpoint
    ENABLE_FEATURE_DOWNLOAD: bool = True
    
    # Status polling endpoint
    ENABLE_FEATURE_STATUS: bool = True
    
    # File download endpoint
    ENABLE_FEATURE_FILE_DOWNLOAD: bool = True
    
    # Task cancellation
    ENABLE_FEATURE_CANCEL: bool = True
    
    # Task deletion
    ENABLE_FEATURE_DELETE: bool = True
    
    # Task listing
    ENABLE_FEATURE_LIST_TASKS: bool = True
    
    # Subtitle download
    ENABLE_FEATURE_SUBTITLES: bool = True
    
    # Thumbnail retrieval
    ENABLE_FEATURE_THUMBNAIL: bool = True
    
    # Queue statistics
    ENABLE_FEATURE_QUEUE_STATS: bool = True
    
    # Progress tracking
    ENABLE_FEATURE_PROGRESS_TRACKING: bool = True
    
    # WebSocket support
    ENABLE_FEATURE_WEBSOCKET: bool = True
    
    # MP3 metadata embedding
    ENABLE_FEATURE_MP3_METADATA: bool = True
    
    # Thumbnail embedding in audio files
    ENABLE_FEATURE_THUMBNAIL_EMBED: bool = True
    
    # GPU encoding support
    ENABLE_FEATURE_GPU_ENCODING: bool = True
    
    # Aria2 downloader support
    ENABLE_FEATURE_ARIA2: bool = True
    
    # Custom format selection
    ENABLE_FEATURE_CUSTOM_FORMAT: bool = True
    
    # Quality selection
    ENABLE_FEATURE_QUALITY_SELECTION: bool = True
    
    # Proxy support
    ENABLE_FEATURE_PROXY: bool = True
    
    # Cookie support
    ENABLE_FEATURE_COOKIES: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
