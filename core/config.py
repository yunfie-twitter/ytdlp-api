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
    REDIS_POOL_SIZE: int = 20
    REDIS_TIMEOUT: int = 5
    
    # ==================== Download Settings ====================
    DOWNLOAD_DIR: str = "./downloads"
    MAX_CONCURRENT_DOWNLOADS: int = 3
    AUTO_DELETE_AFTER: int = 604800  # 7 days
    DOWNLOAD_TIMEOUT: int = 3600  # 1 hour
    
    # ==================== Job Management ====================
    JOB_QUEUE_MAX_SIZE: int = 1000
    JOB_RETRY_ATTEMPTS: int = 3
    JOB_RETRY_BACKOFF: float = 1.5
    JOB_CLEANUP_INTERVAL: int = 3600  # 1 hour
    
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
    YTDLP_SOCKET_TIMEOUT: int = 30
    YTDLP_RETRIES: int = 3
    
    # ==================== Rate Limiting ====================
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # ==================== Timeouts ====================
    VIDEO_INFO_TIMEOUT: int = 30
    SUBTITLE_TIMEOUT: int = 60
    THUMBNAIL_TIMEOUT: int = 30
    API_REQUEST_TIMEOUT: int = 30
    
    # ==================== Security ====================
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # ==================== JWT Authentication ====================
    ENABLE_JWT_AUTH: bool = False
    API_KEY_ISSUE_PASSWORD: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 30
    REDIS_API_KEY_PREFIX: str = "api_key:"
    JWT_VALIDATE_ON_EVERY_REQUEST: bool = True
    
    # ==================== Caching ====================
    ENABLE_CACHING: bool = True
    CACHE_MAX_SIZE: int = 1000
    VIDEO_INFO_CACHE_TTL: int = 3600  # 1 hour
    
    # ==================== Monitoring ====================
    ENABLE_METRICS: bool = True
    METRICS_COLLECTION_INTERVAL: int = 60
    HEALTH_CHECK_INTERVAL: int = 30
    
    # ==================== Feature Flags ====================
    ENABLE_FEATURE_VIDEO_INFO: bool = True
    ENABLE_FEATURE_DOWNLOAD: bool = True
    ENABLE_FEATURE_STATUS: bool = True
    ENABLE_FEATURE_FILE_DOWNLOAD: bool = True
    ENABLE_FEATURE_CANCEL: bool = True
    ENABLE_FEATURE_DELETE: bool = True
    ENABLE_FEATURE_LIST_TASKS: bool = True
    ENABLE_FEATURE_SUBTITLES: bool = True
    ENABLE_FEATURE_THUMBNAIL: bool = True
    ENABLE_FEATURE_QUEUE_STATS: bool = True
    ENABLE_FEATURE_PROGRESS_TRACKING: bool = True
    ENABLE_FEATURE_WEBSOCKET: bool = True
    ENABLE_FEATURE_MP3_METADATA: bool = True
    ENABLE_FEATURE_THUMBNAIL_EMBED: bool = True
    ENABLE_FEATURE_GPU_ENCODING: bool = True
    ENABLE_FEATURE_ARIA2: bool = True
    ENABLE_FEATURE_CUSTOM_FORMAT: bool = True
    ENABLE_FEATURE_QUALITY_SELECTION: bool = True
    ENABLE_FEATURE_PROXY: bool = True
    ENABLE_FEATURE_COOKIES: bool = True
    ENABLE_FEATURE_METRICS: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
