from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 3
    
    # Queue
    MAX_CONCURRENT_DOWNLOADS: int = 3
    
    # Auto-delete
    AUTO_DELETE_AFTER: int = 3600
    
    # Paths
    DOWNLOAD_DIR: str = "/app/downloads"
    
    # yt-dlp
    YTDLP_COOKIES_FILE: Optional[str] = None
    YTDLP_PROXY: Optional[str] = None
    
    # Security
    SECRET_KEY: str
    CORS_ORIGINS: str = "*"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()