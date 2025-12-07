"""Error handling utilities and middleware"""
import logging
import traceback
from typing import Optional, Callable, Any
from functools import wraps
import asyncio

from core.exceptions import APIException, InternalServerError, TimeoutError as TimeoutErrorException

logger = logging.getLogger(__name__)

class ErrorContext:
    """Context manager for error handling and logging"""
    def __init__(self, operation: str, task_id: str = None, log_level: int = logging.ERROR):
        self.operation = operation
        self.task_id = task_id
        self.log_level = log_level
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        
        # Log the error with full context
        context_str = f"[{self.operation}]"
        if self.task_id:
            context_str += f" task_id={self.task_id}"
        
        if issubclass(exc_type, APIException):
            logger.log(self.log_level, f"{context_str} {exc_val}")
            return False  # Re-raise
        else:
            logger.error(
                f"{context_str} Unexpected error: {str(exc_val)}",
                exc_info=True
            )
            return False  # Re-raise

def async_error_handler(
    operation: str,
    default_return: Any = None,
    log_errors: bool = True,
    raise_exception: bool = True
):
    """Decorator for async function error handling"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            task_id = kwargs.get('task_id') or (args[1] if len(args) > 1 else None)
            try:
                return await func(*args, **kwargs)
            except asyncio.TimeoutError:
                msg = f"{operation} timed out"
                if log_errors:
                    logger.warning(f"{msg} (task_id={task_id})")
                if raise_exception:
                    raise TimeoutErrorException(operation, 30)
                return default_return
            except APIException as e:
                if log_errors:
                    logger.warning(f"{operation} failed: {e.message} (task_id={task_id})")
                if raise_exception:
                    raise
                return default_return
            except Exception as e:
                if log_errors:
                    logger.error(
                        f"{operation} failed: {str(e)} (task_id={task_id})",
                        exc_info=True
                    )
                if raise_exception:
                    raise InternalServerError(
                        f"{operation} failed: {str(e)}",
                        details={"operation": operation, "task_id": task_id}
                    )
                return default_return
        return wrapper
    return decorator

def sync_error_handler(
    operation: str,
    default_return: Any = None,
    log_errors: bool = True,
    raise_exception: bool = True
):
    """Decorator for sync function error handling"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except APIException as e:
                if log_errors:
                    logger.warning(f"{operation} failed: {e.message}")
                if raise_exception:
                    raise
                return default_return
            except Exception as e:
                if log_errors:
                    logger.error(
                        f"{operation} failed: {str(e)}",
                        exc_info=True
                    )
                if raise_exception:
                    raise InternalServerError(
                        f"{operation} failed: {str(e)}",
                        details={"operation": operation}
                    )
                return default_return
        return wrapper
    return decorator

class RetryConfig:
    """Configuration for retry logic"""
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay

async def async_retry(
    func: Callable,
    *args,
    config: RetryConfig = None,
    retriable_exceptions: tuple = (Exception,),
    **kwargs
):
    """Retry async function with exponential backoff"""
    config = config or RetryConfig()
    last_exception = None
    delay = config.initial_delay
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except retriable_exceptions as e:
            last_exception = e
            if attempt < config.max_attempts:
                logger.warning(
                    f"Attempt {attempt}/{config.max_attempts} failed: {str(e)}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * config.backoff_factor, config.max_delay)
            else:
                logger.error(
                    f"All {config.max_attempts} attempts failed for {func.__name__}",
                    exc_info=True
                )
    
    raise last_exception

def sync_retry(
    func: Callable,
    *args,
    config: RetryConfig = None,
    retriable_exceptions: tuple = (Exception,),
    **kwargs
):
    """Retry sync function with exponential backoff"""
    config = config or RetryConfig()
    last_exception = None
    delay = config.initial_delay
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except retriable_exceptions as e:
            last_exception = e
            if attempt < config.max_attempts:
                logger.warning(
                    f"Attempt {attempt}/{config.max_attempts} failed: {str(e)}. "
                    f"Retrying in {delay:.1f}s..."
                )
                import time
                time.sleep(delay)
                delay = min(delay * config.backoff_factor, config.max_delay)
            else:
                logger.error(
                    f"All {config.max_attempts} attempts failed for {func.__name__}",
                    exc_info=True
                )
    
    raise last_exception

def log_error_summary(error: Exception, context: str = "") -> str:
    """Generate a detailed error summary for logging"""
    summary = f"Error in {context}\n" if context else "Error occurred\n"
    summary += f"Type: {type(error).__name__}\n"
    summary += f"Message: {str(error)}\n"
    
    if isinstance(error, APIException):
        summary += f"Status Code: {error.status_code}\n"
        summary += f"Error Code: {error.error_code}\n"
        if error.details:
            summary += f"Details: {error.details}\n"
    
    summary += f"Traceback:\n{traceback.format_exc()}"
    return summary
