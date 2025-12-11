"""Performance monitoring and analytics endpoints"""
import logging
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timezone

from core import get_optional_api_key, ErrorContext
from core.performance import performance_monitor, profile
from infrastructure.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/performance", tags=["performance"])

@router.get("/system")
async def get_system_performance(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get system performance metrics"""
    
    with ErrorContext("get_system_performance"):
        stats = await performance_monitor.get_system_stats()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": stats
        }

@router.get("/metrics")
async def get_performance_metrics(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get recorded performance metrics"""
    
    with ErrorContext("get_performance_metrics"):
        metrics = performance_monitor.get_all_stats()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics
        }

@router.get("/cache")
async def get_cache_performance(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get cache performance statistics"""
    
    with ErrorContext("get_cache_performance"):
        from core.cache import cache_manager
        stats = cache_manager.get_stats()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache": stats
        }

@router.get("/quality")
async def get_code_quality(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get code quality metrics"""
    
    with ErrorContext("get_code_quality"):
        from core.error_handling import metrics_collector
        report = metrics_collector.get_quality_report()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "quality": report
        }

@router.get("/recommendations")
async def get_optimization_recommendations(
    api_key: dict = Depends(get_optional_api_key),
    db = Depends(get_db)
):
    """Get optimization recommendations"""
    
    with ErrorContext("get_optimization_recommendations"):
        from core.cache import cache_manager
        recommendations = []
        
        # Check system resources
        stats = await performance_monitor.get_system_stats()
        
        if stats.get("memory", {}).get("healthy") is False:
            recommendations.append({
                "type": "memory",
                "severity": "high",
                "message": "High memory usage detected. Consider garbage collection or optimization."
            })
        
        if stats.get("cpu", {}).get("healthy") is False:
            recommendations.append({
                "type": "cpu",
                "severity": "high",
                "message": "High CPU usage detected. Consider load distribution."
            })
        
        # Check cache performance
        cache_stats = cache_manager.get_stats()
        if float(cache_stats.get("hit_rate", "0%").rstrip("%")) < 30:
            recommendations.append({
                "type": "cache",
                "severity": "medium",
                "message": "Low cache hit rate. Consider caching strategy optimization."
            })
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendations": recommendations
        }
