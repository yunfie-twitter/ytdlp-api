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

class APIError(Exception):
    """Base API error with rich context"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.recoverable = recoverable
        self.timestamp = datetime.now(timezone.utc).isoformat()
        super().__init__(message)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "error": {
                "message": self.message,
                "code": self.error_code,
                "category": self.category.value,
                "severity": self.severity.value,
                "recoverable": self.recoverable,
                "timestamp": self.timestamp,
                "details": self.details
            }
        }

class ValidationError(APIError):
    """Validation error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            details=details
        )

class NetworkError(APIError):
    """Network connectivity error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=503,
            error_code="NETWORK_ERROR",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            details=details,
            recoverable=True
        )

class TaskNotFoundError(APIError):
    """Task not found error"""
    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task not found: {task_id}",
            status_code=404,
            error_code="TASK_NOT_FOUND",
            category=ErrorCategory.NOT_FOUND,
            severity=ErrorSeverity.LOW,
            details={"task_id": task_id}
        )

class InternalServerError(APIError):
    """Internal server error with recovery info"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="INTERNAL_ERROR",
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.CRITICAL,
            details=details
        )

class TimeoutError(APIError):
    """Timeout error"""
    def __init__(self, message: str, operation: str = "", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=504,
            error_code="TIMEOUT",
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.HIGH,
            details={"operation": operation, **(details or {})},
            recoverable=True
        )

class RetryableError(APIError):
    """Retryable error for transient failures"""
    def __init__(
        self,
        message: str,
        retry_after: int = 5,
        max_retries: int = 3,
        details: Optional[Dict] = None
    ):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RETRYABLE_ERROR",
            category=ErrorCategory.RETRY,
            severity=ErrorSeverity.MEDIUM,
            details={
                "retry_after": retry_after,
                "max_retries": max_retries,
                **(details or {})
            },
            recoverable=True
        )

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

def retry(
    max_attempts: int = 3,
    backoff: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,),
    logger_instance: Optional[logging.Logger] = None
):
    """Retry decorator with exponential backoff"""
    _logger = logger_instance or logger
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            attempt = 0
            current_backoff = backoff
            last_exception = None
            
            while attempt < max_attempts:
                try:
                    _logger.debug(f"Attempt {attempt + 1}/{max_attempts} for {func.__name__}")
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    last_exception = e
                    
                    if attempt >= max_attempts:
                        _logger.error(
                            f"Max retries exceeded for {func.__name__}: {str(e)}",
                            exc_info=True
                        )
                        raise RetryableError(
                            f"Operation failed after {max_attempts} attempts",
                            max_retries=max_attempts,
                            details={"function": func.__name__, "error": str(e)}
                        )
                    
                    _logger.warning(
                        f"Retrying {func.__name__} after {current_backoff}s (attempt {attempt}/{max_attempts}): {str(e)}"
                    )
                    await asyncio.sleep(current_backoff)
                    current_backoff *= backoff_multiplier
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            attempt = 0
            current_backoff = backoff
            last_exception = None
            
            while attempt < max_attempts:
                try:
                    _logger.debug(f"Attempt {attempt + 1}/{max_attempts} for {func.__name__}")
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    last_exception = e
                    
                    if attempt >= max_attempts:
                        _logger.error(
                            f"Max retries exceeded for {func.__name__}: {str(e)}",
                            exc_info=True
                        )
                        raise RetryableError(
                            f"Operation failed after {max_attempts} attempts",
                            max_retries=max_attempts,
                            details={"function": func.__name__, "error": str(e)}
                        )
                    
                    _logger.warning(
                        f"Retrying {func.__name__} after {current_backoff}s (attempt {attempt}/{max_attempts}): {str(e)}"
                    )
                    import time
                    time.sleep(current_backoff)
                    current_backoff *= backoff_multiplier
            
            raise last_exception
        
        # Return async wrapper for async functions, sync for sync
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def safe_operation(
    fallback_value: Optional[T] = None,
    logger_instance: Optional[logging.Logger] = None
):
    """Decorator to safely execute operations with fallback"""
    _logger = logger_instance or logger
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                _logger.error(f"Safe operation failed in {func.__name__}: {str(e)}", exc_info=True)
                return fallback_value
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                _logger.error(f"Safe operation failed in {func.__name__}: {str(e)}", exc_info=True)
                return fallback_value
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
