"""Resource pool management for efficient resource handling"""
import logging
import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ResourcePool:
    """Thread-safe resource pool for managing connections and resources"""
    
    def __init__(self, name: str, max_size: int = 10, min_size: int = 2):
        self.name = name
        self.max_size = max_size
        self.min_size = min_size
        self.available: asyncio.Queue = asyncio.Queue(max_size)
        self.in_use: Dict[int, dict] = {}  # Track in-use resources
        self.all_resources: List[int] = []
        self.stats = {
            "created": 0,
            "reused": 0,
            "destroyed": 0,
            "borrowed": 0,
            "returned": 0
        }
    
    async def initialize(self, factory_func) -> None:
        """Initialize pool with minimum resources"""
        for _ in range(self.min_size):
            try:
                resource = await factory_func()
                resource_id = id(resource)
                self.all_resources.append(resource_id)
                await self.available.put(resource)
                self.stats["created"] += 1
                logger.info(f"Pool {self.name}: Created resource {resource_id}")
            except Exception as e:
                logger.error(f"Pool {self.name}: Failed to create resource: {e}")
    
    async def acquire(self, factory_func, timeout: int = 30) -> Optional[object]:
        """Acquire a resource from the pool"""
        try:
            # Try to get existing resource
            if not self.available.empty():
                try:
                    resource = self.available.get_nowait()
                    resource_id = id(resource)
                    self.in_use[resource_id] = {
                        "borrowed_at": datetime.now(timezone.utc).isoformat(),
                        "context": None
                    }
                    self.stats["reused"] += 1
                    logger.debug(f"Pool {self.name}: Reused resource {resource_id}")
                    return resource
                except asyncio.QueueEmpty:
                    pass
            
            # Create new resource if under max size
            if len(self.all_resources) < self.max_size:
                try:
                    resource = await factory_func()
                    resource_id = id(resource)
                    self.all_resources.append(resource_id)
                    self.in_use[resource_id] = {
                        "borrowed_at": datetime.now(timezone.utc).isoformat(),
                        "context": None
                    }
                    self.stats["created"] += 1
                    logger.info(f"Pool {self.name}: Created new resource {resource_id}")
                    return resource
                except Exception as e:
                    logger.error(f"Pool {self.name}: Failed to create resource: {e}")
                    return None
            
            # Wait for resource to become available
            resource = await asyncio.wait_for(
                self.available.get(),
                timeout=timeout
            )
            resource_id = id(resource)
            self.in_use[resource_id] = {
                "borrowed_at": datetime.now(timezone.utc).isoformat(),
                "context": None
            }
            self.stats["borrowed"] += 1
            logger.debug(f"Pool {self.name}: Borrowed resource {resource_id}")
            return resource
        
        except asyncio.TimeoutError:
            logger.warning(f"Pool {self.name}: Timeout waiting for resource")
            return None
    
    async def release(self, resource: object) -> None:
        """Release a resource back to the pool"""
        resource_id = id(resource)
        
        if resource_id not in self.in_use:
            logger.warning(f"Pool {self.name}: Attempted to release unknown resource {resource_id}")
            return
        
        del self.in_use[resource_id]
        
        try:
            self.available.put_nowait(resource)
            self.stats["returned"] += 1
            logger.debug(f"Pool {self.name}: Released resource {resource_id}")
        except asyncio.QueueFull:
            logger.error(f"Pool {self.name}: Queue full, cannot release resource {resource_id}")
    
    async def destroy_all(self, destroy_func) -> None:
        """Destroy all resources in the pool"""
        while not self.available.empty():
            try:
                resource = self.available.get_nowait()
                resource_id = id(resource)
                await destroy_func(resource)
                self.stats["destroyed"] += 1
                logger.info(f"Pool {self.name}: Destroyed resource {resource_id}")
            except asyncio.QueueEmpty:
                break
        
        self.all_resources.clear()
    
    def get_stats(self) -> dict:
        """Get pool statistics"""
        return {
            "name": self.name,
            "available": self.available.qsize(),
            "in_use": len(self.in_use),
            "total": len(self.all_resources),
            "max_size": self.max_size,
            "min_size": self.min_size,
            "stats": self.stats
        }
