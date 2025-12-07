"""Performance optimization utilities and profiling"""
import logging
import asyncio
import time
from typing import Callable, Any, Optional, Dict
from functools import wraps
from datetime import datetime, timezone
import psutil
import gc

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Real-time performance monitoring"""
    
    def __init__(self):
        self.metrics: Dict[str, list] = {}
        self.thresholds: Dict[str, float] = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0
        }
    
    async def get_system_stats(self) -> dict:
        """Get system resource statistics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "threshold": self.thresholds["cpu_percent"],
                    "healthy": cpu_percent < self.thresholds["cpu_percent"]
                },
                "memory": {
                    "percent": memory.percent,
                    "used_gb": memory.used / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "threshold": self.thresholds["memory_percent"],
                    "healthy": memory.percent < self.thresholds["memory_percent"]
                },
                "disk": {
                    "percent": disk.percent,
                    "used_gb": disk.used / (1024**3),
                    "free_gb": disk.free / (1024**3),
                    "threshold": self.thresholds["disk_percent"],
                    "healthy": disk.percent < self.thresholds["disk_percent"]
                }
            }
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {}
    
    def record_metric(self, name: str, value: float, unit: str = "ms") -> None:
        """Record performance metric"""
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append({
            "value": value,
            "unit": unit,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Keep only last 1000 entries
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
    
    def get_metric_stats(self, name: str) -> Optional[dict]:
        """Get statistics for a metric"""
        if name not in self.metrics or not self.metrics[name]:
            return None
        
        values = [m["value"] for m in self.metrics[name]]
        return {
            "name": name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1]
        }
    
    def get_all_stats(self) -> dict:
        """Get statistics for all metrics"""
        return {
            name: self.get_metric_stats(name)
            for name in self.metrics.keys()
        }

class ProfileDecorator:
    """Decorator for profiling function performance"""
    
    def __init__(self, threshold_ms: float = 100.0):
        self.threshold_ms = threshold_ms
        self.monitor = PerformanceMonitor()
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                self.monitor.record_metric(func.__name__, duration_ms)
                
                if duration_ms > self.threshold_ms:
                    logger.warning(
                        f"Slow operation: {func.__name__} took {duration_ms:.2f}ms (threshold: {self.threshold_ms}ms)"
                    )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                self.monitor.record_metric(func.__name__, duration_ms)
                
                if duration_ms > self.threshold_ms:
                    logger.warning(
                        f"Slow operation: {func.__name__} took {duration_ms:.2f}ms (threshold: {self.threshold_ms}ms)"
                    )
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

class ConcurrencyOptimizer:
    """Optimize concurrent operations"""
    
    @staticmethod
    async def gather_with_limit(
        coros: list,
        limit: int = 10,
        return_exceptions: bool = False
    ) -> list:
        """Run coroutines with concurrency limit"""
        semaphore = asyncio.Semaphore(limit)
        
        async def bounded_coro(coro):
            async with semaphore:
                return await coro
        
        return await asyncio.gather(
            *[bounded_coro(coro) for coro in coros],
            return_exceptions=return_exceptions
        )

class MemoryOptimizer:
    """Memory optimization utilities"""
    
    @staticmethod
    def get_memory_usage() -> dict:
        """Get current memory usage"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss_mb": memory_info.rss / (1024**2),
                "vms_mb": memory_info.vms / (1024**2),
                "percent": process.memory_percent()
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {}
    
    @staticmethod
    def collect_garbage() -> dict:
        """Perform garbage collection"""
        collected = gc.collect()
        return {
            "collected_objects": collected,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    async def periodic_gc(interval: int = 300):
        """Run garbage collection periodically"""
        while True:
            try:
                result = MemoryOptimizer.collect_garbage()
                logger.debug(f"Garbage collection: {result['collected_objects']} objects")
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Periodic GC error: {e}")
                await asyncio.sleep(interval)

class QueryOptimizer:
    """Database query optimization"""
    
    @staticmethod
    def optimize_query(query_str: str) -> str:
        """Suggest query optimizations"""
        suggestions = []
        
        if "SELECT *" in query_str:
            suggestions.append("Use specific columns instead of SELECT *")
        
        if "NOT IN" in query_str:
            suggestions.append("Consider using NOT EXISTS for better performance")
        
        if "LIKE '%" in query_str:
            suggestions.append("Leading wildcard LIKE is inefficient, use full-text search")
        
        return "\n".join(suggestions) if suggestions else "Query looks optimized"

# Global instances
performance_monitor = PerformanceMonitor()
profile = ProfileDecorator(threshold_ms=100.0)
