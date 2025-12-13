"""Memory monitoring and leak detection"""
import logging
import os
import psutil
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """Monitor memory usage and detect potential leaks"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.memory_samples: Dict[datetime, float] = {}
        self.leak_threshold_increase_mb = 100  # Alert if increased by 100MB
        self.sample_window_hours = 1
        self.is_leak_detected = False
    
    async def get_memory_stats(self) -> Dict:
        """Get current memory statistics
        
        Returns:
            Dict with memory info
        """
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            return {
                "rss_mb": memory_info.rss / (1024 * 1024),  # Resident Set Size
                "vms_mb": memory_info.vms / (1024 * 1024),  # Virtual Memory Size
                "percent": memory_percent,
                "available_mb": psutil.virtual_memory().available / (1024 * 1024),
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {}
    
    async def monitor_memory(self) -> Dict:
        """Monitor memory and detect anomalies
        
        Returns:
            Dict with monitoring results
        """
        try:
            stats = await self.get_memory_stats()
            if not stats:
                return {}
            
            timestamp = stats["timestamp"]
            rss_mb = stats["rss_mb"]
            
            # Store sample
            self.memory_samples[timestamp] = rss_mb
            
            # Clean old samples
            cutoff = timestamp - timedelta(hours=self.sample_window_hours)
            self.memory_samples = {
                t: v for t, v in self.memory_samples.items()
                if t > cutoff
            }
            
            # Check for memory leak
            if len(self.memory_samples) > 10:
                sorted_samples = sorted(self.memory_samples.values())
                min_mem = sorted_samples[0]
                max_mem = sorted_samples[-1]
                increase = max_mem - min_mem
                
                if increase > self.leak_threshold_increase_mb:
                    self.is_leak_detected = True
                    logger.warning(
                        f"Potential memory leak detected: {increase:.1f}MB increase "
                        f"({min_mem:.1f}MB -> {max_mem:.1f}MB)"
                    )
                else:
                    self.is_leak_detected = False
            
            return {
                **stats,
                "is_leak_detected": self.is_leak_detected,
                "samples_collected": len(self.memory_samples)
            }
        
        except Exception as e:
            logger.error(f"Error monitoring memory: {e}")
            return {}
    
    async def force_garbage_collection(self) -> Dict:
        """Force garbage collection and return stats
        
        Returns:
            Dict with memory stats before/after GC
        """
        import gc
        
        try:
            before = await self.get_memory_stats()
            
            # Force garbage collection
            collected = gc.collect()
            
            after = await self.get_memory_stats()
            
            freed_mb = before["rss_mb"] - after["rss_mb"]
            
            logger.info(
                f"Garbage collection freed {freed_mb:.1f}MB "
                f"(collected {collected} objects)"
            )
            
            return {
                "before_mb": before["rss_mb"],
                "after_mb": after["rss_mb"],
                "freed_mb": freed_mb,
                "objects_collected": collected
            }
        
        except Exception as e:
            logger.error(f"Error forcing garbage collection: {e}")
            return {}


# Global instance
memory_monitor = MemoryMonitor()
