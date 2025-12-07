"""Main FastAPI application factory"""
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from core.config import settings
from core.security import set_redis_manager, is_feature_enabled
from core.jwt_auth import jwt_auth
from infrastructure.database import init_db
from infrastructure.redis_manager import redis_manager
from services.queue_worker import queue_worker
from app.error_responses import register_exception_handlers
from app.endpoints import router as api_router
from app.auth_endpoints import router as auth_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    app = FastAPI(
        title="yt-dlp Download API",
        description="Full-featured video/audio download API with JWT authentication and feature flags",
        version="1.0.5",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json"
    )
    
    # CORS configuration
    allowed_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
    if "*" not in allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE", "PATCH"],
            allow_headers=["Content-Type", "Authorization"],
            max_age=3600,
        )
    else:
        logger.warning("⚠️  CORS is set to allow all origins. This is NOT recommended for production!")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            max_age=3600,
        )
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Register routes
    app.include_router(api_router)
    
    # Register auth routes
    if jwt_auth.is_enabled():
        app.include_router(auth_router)
        logger.info("✓ JWT authentication enabled")
    else:
        logger.info("JWT authentication disabled")
    
    # Health check endpoint
    @app.get("/")
    async def root():
        return {
            "service": "yt-dlp Download API",
            "version": "1.0.5",
            "status": "running",
            "jwt_auth_enabled": jwt_auth.is_enabled(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/health")
    async def health_check():
        try:
            redis_ok = await redis_manager.ping()
            return {
                "status": "healthy" if redis_ok else "degraded",
                "redis": "connected" if redis_ok else "disconnected",
                "jwt_auth": jwt_auth.is_enabled(),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.warning(f"Health check warning: {e}")
            return {
                "status": "degraded",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, 503
    
    # Feature status endpoint
    @app.get("/api/features")
    async def get_feature_status():
        """Get status of all features"""
        return {
            "video_info": is_feature_enabled("video_info"),
            "download": is_feature_enabled("download"),
            "status": is_feature_enabled("status"),
            "file_download": is_feature_enabled("file_download"),
            "cancel": is_feature_enabled("cancel"),
            "delete": is_feature_enabled("delete"),
            "list_tasks": is_feature_enabled("list_tasks"),
            "subtitles": is_feature_enabled("subtitles"),
            "thumbnail": is_feature_enabled("thumbnail"),
            "queue_stats": is_feature_enabled("queue_stats"),
            "websocket": is_feature_enabled("websocket"),
            "mp3_metadata": is_feature_enabled("mp3_metadata"),
            "thumbnail_embed": is_feature_enabled("thumbnail_embed"),
            "gpu_encoding": is_feature_enabled("gpu_encoding"),
            "aria2": is_feature_enabled("aria2"),
            "custom_format": is_feature_enabled("custom_format"),
            "quality_selection": is_feature_enabled("quality_selection"),
            "proxy": is_feature_enabled("proxy"),
            "cookies": is_feature_enabled("cookies")
        }
    
    # Startup event
    @app.on_event("startup")
    async def startup_event():
        try:
            logger.info("Starting up yt-dlp API...")
            init_db()
            logger.info("✓ Database initialized")
            await redis_manager.connect()
            logger.info("✓ Redis connected")
            set_redis_manager(redis_manager)
            asyncio.create_task(queue_worker.start())
            logger.info("✓ Queue worker started")
            
            # Log authentication status
            if jwt_auth.is_enabled():
                if jwt_auth.can_issue_keys():
                    logger.info("✓ JWT authentication enabled (API key issuance enabled)")
                else:
                    logger.info("✓ JWT authentication enabled (API key issuance disabled - set API_KEY_ISSUE_PASSWORD)")
            else:
                logger.info("⚠️  JWT authentication disabled (set ENABLE_JWT_AUTH=true to enable)")
            
            # Log enabled features
            enabled_features = [
                feature.split("_", 1)[1].upper()
                for feature in dir(settings)
                if feature.startswith("ENABLE_FEATURE_") and getattr(settings, feature)
            ]
            logger.info(f"✓ Enabled features: {', '.join(enabled_features)}")
            
            logger.info("✅ yt-dlp API started successfully (v1.0.5)")
        except Exception as e:
            logger.error(f"❌ Failed to start API: {e}", exc_info=True)
            raise
    
    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        try:
            logger.info("Shutting down yt-dlp API...")
            await queue_worker.stop()
            logger.info("✓ Queue worker stopped")
            await redis_manager.disconnect()
            logger.info("✓ Redis disconnected")
            logger.info("👋 yt-dlp API shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    return app

app = create_app()
