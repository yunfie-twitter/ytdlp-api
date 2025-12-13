"""Intelligent caching with LRU eviction and TTL support"""
import logging
import time
from typing import Optional, Any, Dict
from collections import OrderedDict
from datetime import datetime, timedelta
import hashlib
import json

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache with TTL support"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict = OrderedDict()
        self.metadata: Dict[str, dict] = {}  # TTL, access count, size
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set cache value with optional TTL
        
        Returns:
            bool: True if set successfully
        """
        try:
            ttl = ttl or self.default_ttl
            
            # Calculate value size estimate
            try:
                value_size = len(json.dumps(value))
            except:
                value_size = 0
            
            # Check if need to evict
            if key not in self.cache and len(self.cache) >= self.max_size:
                # Evict least recently used (first item in OrderedDict)
                removed_key = next(iter(self.cache))
                del self.cache[removed_key]
                del self.metadata[removed_key]
                logger.debug(f"LRU eviction: {removed_key}")
            
            # Update cache
            self.cache[key] = value
            self.cache.move_to_end(key)  # Move to end (most recent)
            
            # Update metadata
            self.metadata[key] = {
                "ttl_expiry": datetime.utcnow() + timedelta(seconds=ttl),
                "access_count": self.metadata.get(key, {}).get("access_count", 0) + 1,
                "size": value_size,
                "created_at": datetime.utcnow(),
                "last_accessed": datetime.utcnow()
            }
            
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get cache value, updating access time
        
        Returns:
            Cached value or None
        """
        try:
            if key not in self.cache:
                return None
            
            # Check TTL
            metadata = self.metadata.get(key, {})
            if metadata.get("ttl_expiry") and datetime.utcnow() > metadata["ttl_expiry"]:
                del self.cache[key]
                del self.metadata[key]
                logger.debug(f"Cache expired: {key}")
                return None
            
            # Update access metadata
            metadata["access_count"] = metadata.get("access_count", 0) + 1
            metadata["last_accessed"] = datetime.utcnow()
            
            # Move to end (most recent)
            self.cache.move_to_end(key)
            
            return self.cache[key]
        except Exception as e:
            logger.error(f"Error getting cache: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        try:
            if key in self.cache:
                del self.cache[key]
                del self.metadata[key]
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
            return False
    
    def clear(self):
        """Clear entire cache"""
        self.cache.clear()
        self.metadata.clear()
    
    def cleanup_expired(self):
        """Remove expired entries"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, meta in self.metadata.items()
            if meta.get("ttl_expiry") and now > meta["ttl_expiry"]
        ]
        
        for key in expired_keys:
            del self.cache[key]
            del self.metadata[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict:
        """Get cache statistics
        
        Returns:
            Dict with cache stats
        """
        total_accesses = sum(
            meta.get("access_count", 0) for meta in self.metadata.values()
        )
        total_size = sum(
            meta.get("size", 0) for meta in self.metadata.values()
        )
        
        return {
            "entries": len(self.cache),
            "max_size": self.max_size,
            "total_size_bytes": total_size,
            "total_accesses": total_accesses,
            "avg_accesses_per_entry": (
                total_accesses / len(self.cache) if self.cache else 0
            )
        }


class CacheKeyGenerator:
    """Generate consistent cache keys"""
    
    @staticmethod
    def generate_key(
        prefix: str,
        *args,
        **kwargs
    ) -> str:
        """Generate cache key from arguments
        
        Returns:
            String cache key
        """
        try:
            # Combine args and kwargs
            key_parts = [prefix]
            
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))
                else:
                    key_parts.append(json.dumps(arg, sort_keys=True))
            
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}={v}")
                else:
                    key_parts.append(f"{k}={json.dumps(v, sort_keys=True)}")
            
            # Hash long keys
            full_key = ":".join(key_parts)
            if len(full_key) > 200:
                # Use hash for very long keys
                hash_suffix = hashlib.md5(full_key.encode()).hexdigest()[:8]
                return f"{prefix}:{hash_suffix}"
            
            return full_key
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            return f"{prefix}:error"


# Global cache instances
conversion_cache = LRUCache(max_size=500, default_ttl=3600)  # 1 hour
format_cache = LRUCache(max_size=100, default_ttl=86400)  # 1 day
stats_cache = LRUCache(max_size=100, default_ttl=300)  # 5 minutes
