"""Circuit breaker pattern for fault tolerance"""
import logging
from typing import Callable, TypeVar, Optional
from enum import Enum
from datetime import datetime, timezone, timedelta
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker for handling cascading failures"""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
    
    def is_open(self) -> bool:
        """Check if circuit is open"""
        if self.state == CircuitState.CLOSED:
            return False
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.opened_at:
                elapsed = (datetime.now(timezone.utc) - self.opened_at).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.failure_count = 0
                    logger.info(f"Circuit {self.name} transitioning to HALF_OPEN")
                    return False
            return True
        
        # HALF_OPEN state - allow request to test
        return False
    
    def record_success(self):
        """Record successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info(f"Circuit {self.name} recovered and transitioned to CLOSED")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                self.state = CircuitState.OPEN
                self.opened_at = datetime.now(timezone.utc)
                logger.error(
                    f"Circuit {self.name} opened after {self.failure_count} failures. "
                    f"Recovery timeout: {self.recovery_timeout}s"
                )
    
    def get_state(self) -> dict:
        """Get circuit state information"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None
        }

class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ) -> CircuitBreaker:
        """Get or create a circuit breaker"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                name,
                failure_threshold,
                recovery_timeout,
                expected_exception
            )
        return self.breakers[name]
    
    def get_all_states(self) -> dict:
        """Get state of all circuit breakers"""
        return {name: cb.get_state() for name, cb in self.breakers.items()}

def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60
):
    """Decorator for adding circuit breaker to functions"""
    registry = CircuitBreakerRegistry()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker = registry.get_or_create(name, failure_threshold, recovery_timeout)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            if breaker.is_open():
                logger.warning(f"Circuit {name} is open, rejecting request")
                raise RuntimeError(f"Circuit breaker {name} is open")
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            if breaker.is_open():
                logger.warning(f"Circuit {name} is open, rejecting request")
                raise RuntimeError(f"Circuit breaker {name} is open")
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        # Attach breaker info
        if asyncio.iscoroutinefunction(func):
            async_wrapper._breaker = breaker
            return async_wrapper
        else:
            sync_wrapper._breaker = breaker
            return sync_wrapper
    
    return decorator

# Global registry
circuit_breaker_registry = CircuitBreakerRegistry()
