"""Main FastAPI application factory"""
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from core.config import settings
from core.security import set_redis_manager
from infrastructure.database import init_db
from infrastructure.redis_manager import redis_manager
from services.queue_worker import queue_worker
from app.error_responses import register_exception_handlers
from app.endpoints import router

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
        description="Full-featured video/audio download API with queue management",
        version="1.0.4",
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
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
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
    app.include_router(router)
    
    # Health check endpoint
    @app.get("/")
    async def root():
        return {
            "service": "yt-dlp Download API",
            "version": "1.0.4",
            "status": "running",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/health")
    async def health_check():
        try:
            redis_ok = await redis_manager.ping()
            return {
                "status": "healthy" if redis_ok else "degraded",
                "redis": "connected" if redis_ok else "disconnected",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.warning(f"Health check warning: {e}")
            return {
                "status": "degraded",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, 503
    
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
            logger.info("✅ yt-dlp API started successfully (v1.0.4)")
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
