"""Database optimization and query caching"""
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
import hashlib
import json
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class QueryCache:
    """Database query result caching"""
    
    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hit_count = 0
        self.miss_count = 0
    
    def _make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = json.dumps([args, kwargs], sort_keys=True, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, *args, **kwargs) -> Optional[Any]:
        """Get cached result"""
        key = self._make_key(*args, **kwargs)
        
        if key in self.cache:
            entry = self.cache[key]
            
            # Check if expired
            if datetime.now(timezone.utc) > entry["expires_at"]:
                del self.cache[key]
                self.miss_count += 1
                return None
            
            self.hit_count += 1
            return entry["value"]
        
        self.miss_count += 1
        return None
    
    def set(self, value: Any, *args, **kwargs) -> None:
        """Cache query result"""
        # Check size
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k]["created_at"]
            )
            del self.cache[oldest_key]
        
        key = self._make_key(*args, **kwargs)
        self.cache[key] = {
            "value": value,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)
        }
    
    def clear(self) -> None:
        """Clear cache"""
        self.cache.clear()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hit_count,
            "misses": self.miss_count,
            "hit_rate": f"{hit_rate:.1f}%",
            "ttl_seconds": self.ttl_seconds
        }

class IndexAnalyzer:
    """Analyze database index efficiency"""
    
    @staticmethod
    def suggest_indexes(queries: list) -> list:
        """Suggest indexes based on query patterns"""
        suggestions = []
        column_usage = {}
        
        for query in queries:
            # Simple heuristic: look for WHERE clauses
            if "WHERE" in query.upper():
                # Extract column names (simplified)
                parts = query.split()
                for i, part in enumerate(parts):
                    if part.upper() == "WHERE" and i + 1 < len(parts):
                        column = parts[i + 1]
                        column_usage[column] = column_usage.get(column, 0) + 1
        
        # Suggest indexes for frequently used columns
        for column, count in sorted(column_usage.items(), key=lambda x: x[1], reverse=True):
            if count > 3:
                suggestions.append(f"Consider adding index on {column} (used {count} times)")
        
        return suggestions

class BulkOperationOptimizer:
    """Optimize bulk database operations"""
    
    @staticmethod
    def batch_insert(records: list, batch_size: int = 100) -> list:
        """Split records into batches for insertion"""
        batches = []
        for i in range(0, len(records), batch_size):
            batches.append(records[i:i + batch_size])
        return batches
    
    @staticmethod
    def batch_update(updates: list, batch_size: int = 100) -> list:
        """Split updates into batches"""
        batches = []
        for i in range(0, len(updates), batch_size):
            batches.append(updates[i:i + batch_size])
        return batches

class ConnectionPoolOptimizer:
    """Optimize database connection pooling"""
    
    def __init__(self, pool_size: int = 10, max_overflow: int = 20):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.active_connections = 0
        self.connection_history = []
    
    def get_pool_stats(self) -> Dict:
        """Get connection pool statistics"""
        utilization = (self.active_connections / self.pool_size * 100)
        
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "active_connections": self.active_connections,
            "utilization_percent": f"{utilization:.1f}%",
            "available_connections": self.pool_size - self.active_connections
        }

# Global instances
query_cache = QueryCache(max_size=500, ttl_seconds=3600)
