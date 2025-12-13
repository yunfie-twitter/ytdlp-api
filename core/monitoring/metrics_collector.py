"""Performance and health metrics collection"""
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collect and aggregate metrics for monitoring"""
    
    def __init__(self):
        self.operation_times: Dict[str, list] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.operation_counts: Dict[str, int] = defaultdict(int)
        self.retention_window = timedelta(hours=24)
        self.last_cleanup = datetime.utcnow()
    
    def record_operation(
        self,
        operation_name: str,
        duration_seconds: float,
        success: bool = True,
        metadata: Optional[Dict] = None
    ):
        """Record an operation
        
        Args:
            operation_name: Name of operation
            duration_seconds: How long it took
            success: Whether it succeeded
            metadata: Additional info
        """
        try:
            timestamp = datetime.utcnow()
            
            self.operation_times[operation_name].append({
                "timestamp": timestamp,
                "duration": duration_seconds,
                "success": success,
                "metadata": metadata or {}
            })
            
            self.operation_counts[operation_name] += 1
            
            if not success:
                self.error_counts[operation_name] += 1
            
            # Periodically clean old data
            if (datetime.utcnow() - self.last_cleanup) > timedelta(minutes=10):
                self._cleanup_old_data()
        
        except Exception as e:
            logger.error(f"Error recording metric: {e}")
    
    def get_operation_stats(self, operation_name: str) -> Dict:
        """Get statistics for an operation
        
        Returns:
            Dict with operation stats
        """
        try:
            records = self.operation_times.get(operation_name, [])
            
            if not records:
                return {
                    "operation": operation_name,
                    "count": 0,
                    "error_count": 0
                }
            
            durations = [r["duration"] for r in records]
            successful = sum(1 for r in records if r["success"])
            
            return {
                "operation": operation_name,
                "count": self.operation_counts.get(operation_name, 0),
                "error_count": self.error_counts.get(operation_name, 0),
                "success_rate": successful / len(records) if records else 0,
                "avg_duration_ms": (sum(durations) / len(durations)) * 1000 if durations else 0,
                "min_duration_ms": min(durations) * 1000 if durations else 0,
                "max_duration_ms": max(durations) * 1000 if durations else 0,
                "records_collected": len(records)
            }
        
        except Exception as e:
            logger.error(f"Error getting operation stats: {e}")
            return {}
    
    def get_all_stats(self) -> Dict:
        """Get statistics for all operations
        
        Returns:
            Dict with all operation stats
        """
        return {
            op: self.get_operation_stats(op)
            for op in self.operation_times.keys()
        }
    
    def get_health_summary(self) -> Dict:
        """Get overall health summary
        
        Returns:
            Dict with health metrics
        """
        try:
            total_ops = sum(self.operation_counts.values())
            total_errors = sum(self.error_counts.values())
            
            # Calculate error rate
            error_rate = total_errors / total_ops if total_ops > 0 else 0
            
            # Find operations with highest error rate
            worst_operations = []
            for op in self.operation_times.keys():
                stats = self.get_operation_stats(op)
                if stats.get("error_count", 0) > 0:
                    worst_operations.append({
                        "operation": op,
                        "error_count": stats["error_count"],
                        "error_rate": 1 - stats.get("success_rate", 0)
                    })
            
            worst_operations.sort(
                key=lambda x: x["error_count"],
                reverse=True
            )
            
            return {
                "total_operations": total_ops,
                "total_errors": total_errors,
                "overall_error_rate": error_rate,
                "is_healthy": error_rate < 0.05,  # Less than 5% errors
                "worst_operations": worst_operations[:5],
                "tracked_operations": len(self.operation_times)
            }
        
        except Exception as e:
            logger.error(f"Error getting health summary: {e}")
            return {}
    
    def _cleanup_old_data(self):
        """Remove old metric data beyond retention window"""
        try:
            cutoff = datetime.utcnow() - self.retention_window
            
            cleaned_count = 0
            for operation_name in list(self.operation_times.keys()):
                records = self.operation_times[operation_name]
                
                # Remove old records
                new_records = [
                    r for r in records
                    if r["timestamp"] > cutoff
                ]
                
                if len(new_records) < len(records):
                    cleaned_count += len(records) - len(new_records)
                    self.operation_times[operation_name] = new_records
            
            if cleaned_count > 0:
                logger.debug(f"Cleaned up {cleaned_count} old metric records")
            
            self.last_cleanup = datetime.utcnow()
        
        except Exception as e:
            logger.error(f"Error cleaning up metrics: {e}")


class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, metrics: MetricsCollector):
        self.operation_name = operation_name
        self.metrics = metrics
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        success = exc_type is None
        
        self.metrics.record_operation(
            self.operation_name,
            duration,
            success=success,
            metadata={
                "error": str(exc_val) if exc_val else None
            }
        )
        
        return False  # Don't suppress exceptions


# Global instance
metrics_collector = MetricsCollector()
