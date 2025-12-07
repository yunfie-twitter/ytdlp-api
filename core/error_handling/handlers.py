"""Comprehensive error handling and recovery system"""
import logging
from typing import Optional, Dict, Any, Callable, TypeVar
from enum import Enum
from functools import wraps
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(str, Enum):
    """Error categories for classification"""
    VALIDATION = "validation"
    NETWORK = "network"
    IO = "io"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    NOT_FOUND = "not_found"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    RETRY = "retry"
    UNKNOWN = "unknown"

class ErrorContext:
    """Context manager for error handling and logging"""
    
    def __init__(
        self,
        operation: str,
        logger_instance: Optional[logging.Logger] = None,
        **context
    ):
        self.operation = operation
        self.logger = logger_instance or logger
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now(timezone.utc)
        self.logger.info(f"Starting operation: {self.operation}", extra={"context": self.context})
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        if exc_type:
            self.logger.error(
                f"Operation failed: {self.operation}",
                extra={
                    "context": self.context,
                    "error": str(exc_val),
                    "duration": duration
                },
                exc_info=(exc_type, exc_val, exc_tb)
            )
        else:
            self.logger.info(
                f"Operation completed: {self.operation}",
                extra={
                    "context": self.context,
                    "duration": duration
                }
            )
        
        return False

class RetryConfig:
    """Configuration for retry decorator"""
    def __init__(
        self,
        max_attempts: int = 3,
        backoff: float = 1.0,
        backoff_multiplier: float = 2.0,
        exceptions: tuple = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.backoff = backoff
        self.backoff_multiplier = backoff_multiplier
        self.exceptions = exceptions

class RetryableError(Exception):
    """Retryable error for transient failures"""
    def __init__(
        self,
        message: str,
        retry_after: int = 5,
        max_retries: int = 3,
        details: Optional[Dict] = None
    ):
        self.message = message
        self.retry_after = retry_after
        self.max_retries = max_retries
        self.details = details or {}
        super().__init__(message)

def async_error_handler(func):
    """Decorator for async error handling"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            raise
    return wrapper

def sync_error_handler(func):
    """Decorator for sync error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            raise
    return wrapper

def async_retry(config: RetryConfig):
    """Async retry decorator with exponential backoff"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            attempt = 0
            current_backoff = config.backoff
            last_exception = None
            
            while attempt < config.max_attempts:
                try:
                    logger.debug(f"Attempt {attempt + 1}/{config.max_attempts} for {func.__name__}")
                    return await func(*args, **kwargs)
                except config.exceptions as e:
                    attempt += 1
                    last_exception = e
                    
                    if attempt >= config.max_attempts:
                        logger.error(
                            f"Max retries exceeded for {func.__name__}: {str(e)}",
                            exc_info=True
                        )
                        raise RetryableError(
                            f"Operation failed after {config.max_attempts} attempts",
                            max_retries=config.max_attempts,
                            details={"function": func.__name__, "error": str(e)}
                        )
                    
                    logger.warning(
                        f"Retrying {func.__name__} after {current_backoff}s (attempt {attempt}/{config.max_attempts}): {str(e)}"
                    )
                    await asyncio.sleep(current_backoff)
                    current_backoff *= config.backoff_multiplier
            
            raise last_exception
        return wrapper
    return decorator

def sync_retry(config: RetryConfig):
    """Sync retry decorator with exponential backoff"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import time
            attempt = 0
            current_backoff = config.backoff
            last_exception = None
            
            while attempt < config.max_attempts:
                try:
                    logger.debug(f"Attempt {attempt + 1}/{config.max_attempts} for {func.__name__}")
                    return func(*args, **kwargs)
                except config.exceptions as e:
                    attempt += 1
                    last_exception = e
                    
                    if attempt >= config.max_attempts:
                        logger.error(
                            f"Max retries exceeded for {func.__name__}: {str(e)}",
                            exc_info=True
                        )
                        raise RetryableError(
                            f"Operation failed after {config.max_attempts} attempts",
                            max_retries=config.max_attempts,
                            details={"function": func.__name__, "error": str(e)}
                        )
                    
                    logger.warning(
                        f"Retrying {func.__name__} after {current_backoff}s (attempt {attempt}/{config.max_attempts}): {str(e)}"
                    )
                    time.sleep(current_backoff)
                    current_backoff *= config.backoff_multiplier
            
            raise last_exception
        return wrapper
    return decorator

def log_error_summary(errors: list) -> Dict:
    """Generate error summary"""
    return {
        "total_errors": len(errors),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "errors": errors
    }
