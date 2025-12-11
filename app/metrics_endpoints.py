"""System metrics and monitoring endpoints"""
import logging
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timezone

from core import get_optional_api_key, ErrorContext
from infrastructure.redis_manager import redis_manager
from services.queue_worker import queue_worker
from services.job_manager import job_queue
from infrastructure.database import get_db, DownloadTask
from sqlalchemy import func

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("/queue")
async def get_queue_metrics(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get queue metrics and statistics"""
    
    with ErrorContext("get_queue_metrics"):
        active = await redis_manager.get_active_count()
        queued = await redis_manager.get_queue_size()
        
        # Get database stats
        stats = db.query(
            DownloadTask.status,
            func.count(DownloadTask.id).label('count')
        ).group_by(DownloadTask.status).all()
        
        status_counts = {status: count for status, count in stats}
        
        return {
            "active_downloads": active,
            "queued_tasks": queued,
            "status_breakdown": status_counts,
            "capacity_usage": f"{(active / 10) * 100:.1f}%"  # Assuming max is 10
        }

@router.get("/worker")
async def get_worker_metrics(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get queue worker performance metrics"""
    
    with ErrorContext("get_worker_metrics"):
        stats = queue_worker.get_stats()
        
        return {
            "worker": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@router.get("/jobs")
async def get_job_metrics(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get job queue metrics"""
    
    with ErrorContext("get_job_metrics"):
        stats = await job_queue.get_stats()
        
        return {
            "queue": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@router.get("/system")
async def get_system_metrics(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get overall system metrics"""
    
    with ErrorContext("get_system_metrics"):
        # Queue metrics
        active = await redis_manager.get_active_count()
        queued = await redis_manager.get_queue_size()
        
        # Worker metrics
        worker_stats = queue_worker.get_stats()
        
        # Job metrics
        job_stats = await job_queue.get_stats()
        
        # Task metrics
        task_stats = db.query(
            DownloadTask.status,
            func.count(DownloadTask.id).label('count')
        ).group_by(DownloadTask.status).all()
        
        status_breakdown = {status: count for status, count in task_stats}
        total_tasks = sum(status_breakdown.values())
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "queue": {
                "active": active,
                "queued": queued
            },
            "worker": {
                "running": worker_stats["running"],
                "success_rate": f"{worker_stats['success_rate']:.1f}%",
                "tasks_processed": worker_stats["tasks_processed"]
            },
            "jobs": {
                "active": job_stats["active"],
                "queued": job_stats["queued"],
                "completed": job_stats["completed"]
            },
            "tasks": {
                "total": total_tasks,
                "breakdown": status_breakdown
            }
        }

@router.get("/performance")
async def get_performance_metrics(
    time_window: int = Query(3600, ge=60, le=86400),
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get performance metrics over time window"""
    
    with ErrorContext("get_performance_metrics"):
        worker_stats = queue_worker.get_stats()
        
        # Calculate performance indicators
        avg_duration = worker_stats.get("average_duration", 0)
        success_rate = worker_stats.get("success_rate", 0)
        
        return {
            "time_window_seconds": time_window,
            "performance": {
                "average_task_duration": f"{avg_duration:.2f}s",
                "success_rate": f"{success_rate:.1f}%",
                "tasks_per_hour": worker_stats["tasks_processed"] / (worker_stats["uptime"] / 3600) if worker_stats["uptime"] > 0 else 0,
                "uptime_hours": worker_stats["uptime"] / 3600
            },
            "health": {
                "error_count": worker_stats["error_count"],
                "last_error": worker_stats["last_error"]
            }
        }
