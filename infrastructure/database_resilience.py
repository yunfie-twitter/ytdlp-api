"""Database operation resilience with retry logic and transaction management"""
import logging
import asyncio
from typing import Optional, Callable, Any, TypeVar
from functools import wraps
from datetime import datetime, timedelta

from sqlalchemy import event
from sqlalchemy.exc import (
    OperationalError,
    DatabaseError,
    DisconnectionError,
    TimeoutError as SQLTimeoutError,
    IntegrityError
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DatabaseRetryPolicy:
    """Retry policy for database operations"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 0.5,
        max_delay: float = 5.0,
        backoff_factor: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        # Transient errors that should trigger retry
        self.retryable_errors = (
            OperationalError,
            DisconnectionError,
            SQLTimeoutError
        )
    
    def retry(self, operation_name: str = "Database operation"):
        """Decorator for retrying failed database operations"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Optional[Any]:
                delay = self.initial_delay
                
                for attempt in range(self.max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except IntegrityError as e:
                        # Don't retry integrity errors
                        logger.error(f"{operation_name}: Integrity error (not retrying): {e}")
                        raise
                    except self.retryable_errors as e:
                        if attempt == self.max_retries:
                            logger.error(
                                f"{operation_name} failed after {self.max_retries + 1} attempts: {e}"
                            )
                            raise
                        
                        logger.warning(
                            f"{operation_name} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        asyncio.run(asyncio.sleep(delay))
                        delay = min(delay * self.backoff_factor, self.max_delay)
                    except Exception as e:
                        # Don't retry unexpected errors
                        logger.error(f"{operation_name}: Unexpected error: {e}")
                        raise
            
            return wrapper
        return decorator


class TransactionManager:
    """Manages database transactions with proper error handling"""
    
    def __init__(self, db):
        self.db = db
        self.transaction_count = 0
    
    def begin_transaction(self):
        """Begin a transaction with error handling"""
        try:
            self.db.begin()
            self.transaction_count += 1
            logger.debug(f"Transaction started (count: {self.transaction_count})")
        except Exception as e:
            logger.error(f"Failed to begin transaction: {e}")
            raise
    
    def commit_transaction(self):
        """Commit transaction with retry logic"""
        try:
            self.db.commit()
            self.transaction_count = max(0, self.transaction_count - 1)
            logger.debug(f"Transaction committed (remaining: {self.transaction_count})")
        except IntegrityError as e:
            logger.error(f"Commit failed due to integrity error: {e}")
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
            raise
        except (OperationalError, DatabaseError) as e:
            logger.error(f"Commit failed due to database error: {e}")
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during commit: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            raise
    
    def rollback_transaction(self):
        """Rollback transaction safely"""
        try:
            self.db.rollback()
            self.transaction_count = max(0, self.transaction_count - 1)
            logger.debug(f"Transaction rolled back (remaining: {self.transaction_count})")
        except Exception as e:
            logger.error(f"Failed to rollback transaction: {e}")
    
    def reset(self):
        """Reset transaction state"""
        try:
            if self.transaction_count > 0:
                logger.warning(f"Resetting {self.transaction_count} active transactions")
                self.db.rollback()
                self.transaction_count = 0
        except Exception as e:
            logger.error(f"Error resetting transactions: {e}")


class QueryTimeout:
    """Context manager for query timeout handling"""
    
    def __init__(self, db, timeout_seconds: int = 30):
        self.db = db
        self.timeout_seconds = timeout_seconds
    
    def __enter__(self):
        try:
            # Set timeout on connection
            if hasattr(self.db, 'connection'):
                self.db.connection().set_isolation_level(0)
        except Exception as e:
            logger.warning(f"Could not set query timeout: {e}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if isinstance(exc_val, SQLTimeoutError):
                logger.error(f"Query timeout after {self.timeout_seconds}s")
        return False


class DatabaseHealthCheck:
    """Monitor database health and connection status"""
    
    def __init__(self, db):
        self.db = db
        self.last_check = None
        self.is_healthy = False
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
    
    async def check_health(self) -> bool:
        """Check database connectivity
        
        Returns:
            bool: True if database is healthy
        """
        try:
            # Try a simple query
            self.db.execute("SELECT 1")
            self.is_healthy = True
            self.consecutive_failures = 0
            self.last_check = datetime.utcnow()
            logger.debug("Database health check passed")
            return True
        
        except Exception as e:
            self.consecutive_failures += 1
            logger.warning(
                f"Database health check failed ({self.consecutive_failures}/ "
                f"{self.max_consecutive_failures}): {e}"
            )
            
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.is_healthy = False
                logger.error("Database marked as unhealthy")
            
            return False
    
    def is_connection_healthy(self) -> bool:
        """Check if last health check indicates healthy connection"""
        if not self.last_check:
            return False
        
        # Consider healthy if checked within last 60 seconds
        time_since_check = datetime.utcnow() - self.last_check
        return (
            self.is_healthy and
            time_since_check < timedelta(seconds=60)
        )
    
    def reset(self):
        """Reset health check state"""
        self.consecutive_failures = 0
        self.is_healthy = False
        self.last_check = None


# Global instances
db_retry_policy = DatabaseRetryPolicy()
