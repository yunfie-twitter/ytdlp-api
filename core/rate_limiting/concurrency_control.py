"""Advanced concurrency control and rate limiting"""
import logging
import asyncio
from typing import Optional, Dict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time

logger = logging.getLogger(__name__)


class ConcurrencyLimiter:
    """Limit concurrent operations with queuing"""
    
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.active_count = 0
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.wait_queue: deque = deque()
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_wait_time": 0
        }
    
    async def acquire(self, task_id: str = None) -> None:
        """Acquire concurrency slot
        
        Args:
            task_id: Optional task identifier for logging
        """
        wait_start = time.time()
        self.wait_queue.append(task_id or "unknown")
        
        await self.semaphore.acquire()
        
        wait_time = time.time() - wait_start
        self.stats["total_wait_time"] += wait_time
        
        if wait_time > 1:
            logger.debug(
                f"Task {task_id or 'unknown'} waited {wait_time:.2f}s "
                f"({len(self.wait_queue)} in queue)"
            )
        
        self.active_count += 1
        self.stats["total_tasks"] += 1
    
    def release(self) -> None:
        """Release concurrency slot"""
        if self.wait_queue:
            self.wait_queue.popleft()
        
        self.active_count = max(0, self.active_count - 1)
        self.semaphore.release()
        self.stats["completed_tasks"] += 1
    
    def record_failure(self) -> None:
        """Record task failure"""
        self.stats["failed_tasks"] += 1
    
    def get_stats(self) -> Dict:
        """Get concurrency statistics
        
        Returns:
            Dict with stats
        """
        return {
            **self.stats,
            "active_tasks": self.active_count,
            "queued_tasks": len(self.wait_queue),
            "max_concurrent": self.max_concurrent,
            "avg_wait_time": (
                self.stats["total_wait_time"] / self.stats["total_tasks"]
                if self.stats["total_tasks"] > 0 else 0
            )
        }


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(
        self,
        rate: int,
        window_seconds: int = 60
    ):
        """Initialize rate limiter
        
        Args:
            rate: Operations per window
            window_seconds: Window size in seconds
        """
        self.rate = rate
        self.window_seconds = window_seconds
        self.tokens = rate
        self.last_update = time.time()
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    async def acquire(self, client_id: str = None) -> float:
        """Acquire rate limit token
        
        Returns:
            Time waited in seconds
        """
        wait_time = 0
        
        while True:
            now = time.time()
            elapsed = now - self.last_update
            
            # Refill tokens
            refill = (elapsed / self.window_seconds) * self.rate
            self.tokens = min(self.rate, self.tokens + refill)
            self.last_update = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                
                # Track request
                if client_id:
                    self.requests[client_id].append(now)
                    
                    # Clean old requests
                    cutoff = now - self.window_seconds
                    while self.requests[client_id] and self.requests[client_id][0] < cutoff:
                        self.requests[client_id].popleft()
                
                return wait_time
            
            # Wait for token
            wait_amount = (1 - self.tokens) * self.window_seconds / self.rate
            await asyncio.sleep(min(wait_amount, 0.1))
            wait_time += min(wait_amount, 0.1)
    
    def get_client_request_count(self, client_id: str) -> int:
        """Get request count for a client in current window
        
        Returns:
            Number of requests
        """
        now = time.time()
        cutoff = now - self.window_seconds
        
        while self.requests[client_id] and self.requests[client_id][0] < cutoff:
            self.requests[client_id].popleft()
        
        return len(self.requests[client_id])


class CircuitBreaker:
    """Circuit breaker for failing operations"""
    
    class State:
        CLOSED = "closed"    # Normal operation
        OPEN = "open"        # Failing, reject requests
        HALF_OPEN = "half_open"  # Testing recovery
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        self.state = self.State.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.utcnow()
    
    def record_success(self) -> None:
        """Record successful operation"""
        if self.state == self.State.HALF_OPEN:
            logger.info(f"Circuit breaker CLOSED (recovered)")
            self.state = self.State.CLOSED
            self.failure_count = 0
        
        elif self.state == self.State.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self) -> None:
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != self.State.OPEN:
                logger.warning(
                    f"Circuit breaker OPEN ({self.failure_count} failures)"
                )
                self.state = self.State.OPEN
                self.last_state_change = datetime.utcnow()
    
    def can_execute(self) -> bool:
        """Check if operation can execute
        
        Returns:
            bool: True if can execute
        """
        if self.state == self.State.CLOSED:
            return True
        
        if self.state == self.State.OPEN:
            # Check if recovery timeout elapsed
            if datetime.utcnow() - self.last_state_change > self.recovery_timeout:
                logger.info(f"Circuit breaker HALF_OPEN (recovery attempt)")
                self.state = self.State.HALF_OPEN
                self.failure_count = 0
                return True
            return False
        
        if self.state == self.State.HALF_OPEN:
            return True
        
        return False
    
    def get_state(self) -> Dict:
        """Get circuit breaker state
        
        Returns:
            Dict with state info
        """
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_state_change": self.last_state_change.isoformat()
        }


# Global instances
conversion_limiter = ConcurrencyLimiter(max_concurrent=2)
api_rate_limiter = RateLimiter(rate=100, window_seconds=60)
conversion_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout_seconds=300
)
