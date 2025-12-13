"""Connection pooling with monitoring and optimization"""
import logging
from typing import Optional, Dict
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ConnectionPoolMonitor:
    """Monitor database and Redis connection pools"""
    
    def __init__(self):
        self.db_pool_stats: Dict = {}
        self.redis_pool_stats: Dict = {}
        self.last_check = None
    
    async def get_db_pool_stats(self, db_pool) -> Dict:
        """Get database connection pool statistics
        
        Returns:
            Dict with pool stats
        """
        try:
            stats = {
                "pool_size": db_pool.pool.size() if hasattr(db_pool.pool, 'size') else 0,
                "checked_in": db_pool.pool.checkedin() if hasattr(db_pool.pool, 'checkedin') else 0,
                "checked_out": db_pool.pool.checkedout() if hasattr(db_pool.pool, 'checkedout') else 0,
                "overflow": db_pool.pool.overflow() if hasattr(db_pool.pool, 'overflow') else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Check pool utilization
            if stats["pool_size"] > 0:
                utilization = (stats["checked_out"] / stats["pool_size"]) * 100
                stats["utilization_percent"] = utilization
                
                if utilization > 80:
                    logger.warning(
                        f"Database pool utilization high: {utilization:.1f}% "
                        f"({stats['checked_out']}/{stats['pool_size']})"
                    )
            
            self.db_pool_stats = stats
            return stats
        
        except Exception as e:
            logger.error(f"Error getting DB pool stats: {e}")
            return {}
    
    async def get_redis_pool_stats(self, redis_client) -> Dict:
        """Get Redis connection pool statistics
        
        Returns:
            Dict with pool stats
        """
        try:
            if not redis_client:
                return {}
            
            connection_pool = redis_client.connection_pool
            
            stats = {
                "max_connections": connection_pool.max_connections,
                "created_connections": len(connection_pool._created_connections) if hasattr(connection_pool, '_created_connections') else 0,
                "available": connection_pool._available_connections if hasattr(connection_pool, '_available_connections') else 0,
                "in_use": len(connection_pool._in_use_connections) if hasattr(connection_pool, '_in_use_connections') else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Calculate utilization
            if stats["max_connections"] > 0:
                in_use = stats["in_use"] + len(connection_pool._in_use_connections) if hasattr(connection_pool, '_in_use_connections') else 0
                utilization = (in_use / stats["max_connections"]) * 100
                stats["utilization_percent"] = utilization
                
                if utilization > 80:
                    logger.warning(
                        f"Redis pool utilization high: {utilization:.1f}% "
                        f"({in_use}/{stats['max_connections']})"
                    )
            
            self.redis_pool_stats = stats
            return stats
        
        except Exception as e:
            logger.error(f"Error getting Redis pool stats: {e}")
            return {}
    
    async def health_check_connections(self, db_pool, redis_client) -> Dict:
        """Health check all connections
        
        Returns:
            Dict with health status
        """
        health = {
            "database": False,
            "redis": False,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check database
        try:
            db_pool.execute("SELECT 1")
            health["database"] = True
            logger.debug("Database connection healthy")
        except Exception as e:
            logger.error(f"Database connection unhealthy: {e}")
        
        # Check Redis
        try:
            if redis_client:
                redis_client.ping()
                health["redis"] = True
                logger.debug("Redis connection healthy")
        except Exception as e:
            logger.error(f"Redis connection unhealthy: {e}")
        
        return health


class PoolOptimizer:
    """Optimize connection pool settings"""
    
    @staticmethod
    def recommend_pool_size(expected_concurrent_requests: int) -> Dict:
        """Recommend optimal pool size based on expected load
        
        Returns:
            Dict with recommended settings
        """
        # Database connections: typically 1.5-2x concurrent requests
        db_pool_size = max(5, int(expected_concurrent_requests * 1.5))
        db_pool_max_overflow = max(10, int(expected_concurrent_requests * 0.5))
        
        # Redis connections: typically less than database
        redis_pool_size = max(5, int(expected_concurrent_requests * 0.75))
        
        return {
            "database": {
                "pool_size": db_pool_size,
                "max_overflow": db_pool_max_overflow,
                "pool_recycle": 3600,  # Recycle connections every hour
                "pool_pre_ping": True   # Verify connections before use
            },
            "redis": {
                "max_connections": redis_pool_size,
                "socket_keepalive": True,
                "socket_keepalive_options": {
                    1: (9, 1, 3)  # TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT
                }
            }
        }
    
    @staticmethod
    def apply_performance_tuning(db_pool) -> bool:
        """Apply performance tuning to database pool
        
        Returns:
            bool: True if tuning applied
        """
        try:
            # Enable connection validation
            if hasattr(db_pool, 'pre_ping'):
                db_pool.pre_ping = True
            
            # Set echo for debugging (disable in production)
            # db_pool.echo = False
            
            logger.info("Performance tuning applied to database pool")
            return True
        except Exception as e:
            logger.error(f"Error applying performance tuning: {e}")
            return False


# Global instances
pool_monitor = ConnectionPoolMonitor()
pool_optimizer = PoolOptimizer()
