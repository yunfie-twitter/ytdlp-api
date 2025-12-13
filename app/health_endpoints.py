"""Health check and diagnostics endpoints"""
import logging
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException

from core.monitoring.memory_monitor import memory_monitor
from core.monitoring.metrics_collector import metrics_collector
from core.logging.structured_logging import get_context
from infrastructure.connection_pool import pool_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint
    
    Returns:
        Dict with health status
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.get("/memory")
async def memory_health() -> Dict[str, Any]:
    """Get memory health information
    
    Returns:
        Dict with memory stats
    """
    try:
        stats = await memory_monitor.monitor_memory()
        
        return {
            "status": "healthy" if not stats.get("is_leak_detected") else "warning",
            "memory_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """Get application metrics
    
    Returns:
        Dict with performance metrics
    """
    try:
        health_summary = metrics_collector.get_health_summary()
        all_stats = metrics_collector.get_all_stats()
        
        return {
            "health_summary": health_summary,
            "operations": all_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Metrics check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/database")
async def database_health(db_pool=None) -> Dict[str, Any]:
    """Get database health status
    
    Returns:
        Dict with DB stats
    """
    try:
        if db_pool is None:
            return {
                "status": "unknown",
                "message": "Database pool not configured",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        stats = await pool_monitor.get_db_pool_stats(db_pool)
        health = await pool_monitor.health_check_connections(db_pool, None)
        
        return {
            "status": "healthy" if health.get("database") else "unhealthy",
            "pool_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/redis")
async def redis_health(redis_client=None) -> Dict[str, Any]:
    """Get Redis health status
    
    Returns:
        Dict with Redis stats
    """
    try:
        if redis_client is None:
            return {
                "status": "unknown",
                "message": "Redis not configured",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        stats = await pool_monitor.get_redis_pool_stats(redis_client)
        health = await pool_monitor.health_check_connections(None, redis_client)
        
        return {
            "status": "healthy" if health.get("redis") else "unhealthy",
            "pool_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/deep")
async def deep_health_check(db_pool=None, redis_client=None) -> Dict[str, Any]:
    """Comprehensive health check of all systems
    
    Returns:
        Dict with complete system health
    """
    try:
        memory_stats = await memory_monitor.monitor_memory()
        metrics_summary = metrics_collector.get_health_summary()
        context = get_context()
        
        # Determine overall status
        is_healthy = (
            not memory_stats.get("is_leak_detected") and
            metrics_summary.get("is_healthy", True)
        )
        
        return {
            "status": "healthy" if is_healthy else "warning",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "memory": {
                    "status": "healthy" if not memory_stats.get("is_leak_detected") else "warning",
                    "rss_mb": memory_stats.get("rss_mb"),
                    "leak_detected": memory_stats.get("is_leak_detected", False)
                },
                "metrics": {
                    "status": "healthy" if metrics_summary.get("is_healthy") else "warning",
                    "error_rate": metrics_summary.get("overall_error_rate", 0),
                    "total_operations": metrics_summary.get("total_operations", 0)
                },
                "context": context
            }
        }
    except Exception as e:
        logger.error(f"Deep health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes readiness probe
    
    Returns:
        Dict with readiness status
    """
    try:
        # Check critical components
        metrics_summary = metrics_collector.get_health_summary()
        
        is_ready = metrics_summary.get("is_healthy", True)
        
        if is_ready:
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=503, detail="Not ready")
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe
    
    Returns:
        Dict with liveness status
    """
    try:
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not alive")
