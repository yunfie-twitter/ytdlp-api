"""Configuration management using Pydantic Settings"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    # API settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    # Database
    DATABASE_URL: str = "sqlite:///./download_tasks.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Download settings
    DOWNLOAD_DIR: str = "./downloads"
    MAX_CONCURRENT_DOWNLOADS: int = 3
    AUTO_DELETE_AFTER: int = 604800  # 7 days
    
    # GPU Encoding
    ENABLE_GPU_ENCODING: bool = False
    GPU_ENCODER_TYPE: str = "auto"  # auto, nvenc, vaapi, qsv
    GPU_ENCODER_PRESET: str = "fast"  # fast, medium, slow
    
    # Aria2
    ENABLE_ARIA2: bool = False
    ARIA2_MAX_CONNECTIONS: int = 4
    ARIA2_SPLIT: int = 4
    
    # Deno/JavaScript runtime
    ENABLE_DENO: bool = False
    DENO_PATH: str = "/usr/local/bin/deno"
    
    # yt-dlp settings
    YTDLP_PROXY: Optional[str] = None
    YTDLP_COOKIES_FILE: Optional[str] = None
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
