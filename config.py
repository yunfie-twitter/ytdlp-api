from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Server
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port", ge=1, le=65535)
    
    # Database
    DATABASE_URL: str = Field(description="Database connection URL")
    
    # Redis
    REDIS_URL: str = Field(description="Redis connection URL")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=3, description="Max requests per minute per IP", ge=1)
    
    # Queue
    MAX_CONCURRENT_DOWNLOADS: int = Field(default=3, description="Maximum concurrent downloads", ge=1, le=10)
    
    # Auto-delete
    AUTO_DELETE_AFTER: int = Field(default=3600, description="Auto-delete completed files after (seconds)", ge=300)
    
    # Paths
    DOWNLOAD_DIR: str = Field(default="/app/downloads", description="Directory to store downloads")
    
    # yt-dlp
    YTDLP_COOKIES_FILE: Optional[str] = Field(default=None, description="Path to yt-dlp cookies file")
    YTDLP_PROXY: Optional[str] = Field(default=None, description="Proxy URL for yt-dlp")
    
    # GPU Encoding Support
    ENABLE_GPU_ENCODING: bool = Field(default=False, description="Enable GPU encoding")
    GPU_ENCODER_TYPE: str = Field(default="auto", description="GPU encoder type (auto, nvenc, vaapi, qsv)")
    GPU_ENCODER_PRESET: str = Field(default="medium", description="GPU encoder preset (fast, medium, slow)")
    
    # aria2 External Downloader
    ENABLE_ARIA2: bool = Field(default=False, description="Enable aria2 for downloads")
    ARIA2_MAX_CONNECTIONS: int = Field(default=16, description="Max connections for aria2", ge=1)
    ARIA2_SPLIT: int = Field(default=16, description="Split count for aria2", ge=1)
    
    # Deno JavaScript Runtime
    ENABLE_DENO: bool = Field(default=False, description="Enable Deno runtime support")
    DENO_PATH: str = Field(default="/usr/local/bin/deno", description="Path to Deno binary")
    
    # Security
    SECRET_KEY: str = Field(description="Secret key for security")
    CORS_ORIGINS: str = Field(default="*", description="CORS origins (comma-separated)")
    
    @field_validator('GPU_ENCODER_TYPE')
    @classmethod
    def validate_encoder_type(cls, v):
        valid_types = ["auto", "nvenc", "vaapi", "qsv"]
        if v not in valid_types:
            raise ValueError(f"GPU_ENCODER_TYPE must be one of {valid_types}")
        return v
    
    @field_validator('GPU_ENCODER_PRESET')
    @classmethod
    def validate_encoder_preset(cls, v):
        valid_presets = ["fast", "medium", "slow"]
        if v not in valid_presets:
            raise ValueError(f"GPU_ENCODER_PRESET must be one of {valid_presets}")
        return v
    
    @field_validator('DOWNLOAD_DIR')
    @classmethod
    def validate_download_dir(cls, v):
        if not v:
            raise ValueError("DOWNLOAD_DIR cannot be empty")
        return v
    
    @field_validator('PORT')
    @classmethod
    def validate_port(cls, v):
        if v < 1 or v > 65535:
            raise ValueError("PORT must be between 1 and 65535")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True

try:
    settings = Settings()
    logger.info("Configuration loaded successfully")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise