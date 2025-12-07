"""Comprehensive monitoring and health check system"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class HealthStatus(str, Enum):
    """Health status indicators"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class HealthCheckComponent:
    """Base class for health check components"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = HealthStatus.UNKNOWN
        self.last_check: Optional[datetime] = None
        self.details: Dict = {}
    
    async def check(self) -> HealthStatus:
        """Override in subclasses"""
        raise NotImplementedError
    
    async def run_check(self) -> dict:
        """Run health check and update status"""
        try:
            self.status = await self.check()
            self.last_check = datetime.now(timezone.utc)
        except Exception as e:
            self.status = HealthStatus.UNHEALTHY
            self.details["error"] = str(e)
            logger.error(f"Health check failed for {self.name}: {e}")
        
        return self.get_status()
    
    def get_status(self) -> dict:
        """Get component status"""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "details": self.details
        }

class HealthMonitor:
    """Central health monitoring system"""
    
    def __init__(self):
        self.components: Dict[str, HealthCheckComponent] = {}
        self.overall_status = HealthStatus.UNKNOWN
    
    def register_component(self, component: HealthCheckComponent) -> None:
        """Register a health check component"""
        self.components[component.name] = component
        logger.info(f"Registered health component: {component.name}")
    
    async def check_all(self) -> dict:
        """Run all health checks"""
        results = []
        
        for component in self.components.values():
            status = await component.run_check()
            results.append(status)
        
        # Calculate overall status
        statuses = [r["status"] for r in results]
        
        if HealthStatus.UNHEALTHY.value in statuses:
            self.overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED.value in statuses:
            self.overall_status = HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY.value for s in statuses):
            self.overall_status = HealthStatus.HEALTHY
        else:
            self.overall_status = HealthStatus.UNKNOWN
        
        return {
            "overall": self.overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": results
        }
    
    def get_status(self) -> dict:
        """Get current health status (cached)"""
        return {
            "overall": self.overall_status.value,
            "components": [c.get_status() for c in self.components.values()]
        }

# Global instance
health_monitor = HealthMonitor()
