"""Intelligent caching system for performance optimization"""
import logging
import asyncio
from typing import Optional, Dict, Any, Callable, TypeVar
from datetime import datetime, timezone, timedelta
import hashlib
import json

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CacheEntry:
    """Single cache entry with TTL and metadata"""
    
    def __init__(self, value: Any, ttl: int = 3600):
        self.value = value
        self.created_at = datetime.now(timezone.utc)
        self.ttl = ttl
        self.accessed_at = self.created_at
        self.access_count = 0
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl
    
    def access(self) -> Any:
        """Access the cached value"""
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1
        return self.value

class CacheManager:
    """Local cache manager with TTL and statistics"""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
    
    def _make_key(self, namespace: str, *args) -> str:
        """Generate cache key"""
        key_data = json.dumps([namespace, *args], sort_keys=True, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, namespace: str, *args) -> Optional[Any]:
        """Get cached value"""
        key = self._make_key(namespace, *args)
        
        if key in self.cache:
            entry = self.cache[key]
            
            if entry.is_expired():
                del self.cache[key]
                self.stats["misses"] += 1
                return None
            
            self.stats["hits"] += 1
            return entry.access()
        
        self.stats["misses"] += 1
        return None
    
    async def set(self, namespace: str, ttl: int = 3600, *args, **kwargs) -> None:
        """Set cached value"""
        value = kwargs.get("value")
        if value is None:
            return
        
        # Check size and evict LRU if needed
        if len(self.cache) >= self.max_size:
            # Find least recently used
            lru_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].accessed_at
            )
            del self.cache[lru_key]
            self.stats["evictions"] += 1
        
        key = self._make_key(namespace, *args)
        self.cache[key] = CacheEntry(value, ttl)
    
    async def invalidate(self, namespace: str, *args) -> bool:
        """Invalidate cache entry"""
        key = self._make_key(namespace, *args)
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    async def clear(self) -> int:
        """Clear all cache"""
        count = len(self.cache)
        self.cache.clear()
        return count
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries"""
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": f"{hit_rate:.2f}%",
            "evictions": self.stats["evictions"]
        }

# Global instance
cache_manager = CacheManager()
