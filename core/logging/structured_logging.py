"""Structured logging with correlation IDs and context"""
import logging
import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from contextvars import ContextVar
import traceback

# Context variables for correlation tracking
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')
task_id_var: ContextVar[str] = ContextVar('task_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')


class StructuredFormatter(logging.Formatter):
    """Formats log records as structured JSON"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON
        
        Returns:
            JSON string
        """
        try:
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                # Context
                "correlation_id": correlation_id_var.get(),
                "task_id": task_id_var.get(),
                "user_id": user_id_var.get(),
            }
            
            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = {
                    "type": record.exc_info[0].__name__,
                    "message": str(record.exc_info[1]),
                    "traceback": traceback.format_exception(*record.exc_info)
                }
            
            # Add extra fields
            if hasattr(record, 'context_data'):
                log_data["context"] = record.context_data
            
            return json.dumps(log_data, default=str)
        
        except Exception as e:
            # Fallback to standard format if JSON encoding fails
            return f"[LOG ERROR] {record.getMessage()}: {e}"


class ContextualLogger(logging.Logger):
    """Logger with built-in context support"""
    
    def _log(
        self,
        level: int,
        msg: str,
        args: tuple,
        exc_info=None,
        extra=None,
        stack_info=False,
        **kwargs
    ):
        """Log with automatic context injection"""
        if extra is None:
            extra = {}
        
        # Inject context data
        context_data = {}
        if correlation_id := correlation_id_var.get():
            context_data["correlation_id"] = correlation_id
        if task_id := task_id_var.get():
            context_data["task_id"] = task_id
        if user_id := user_id_var.get():
            context_data["user_id"] = user_id
        
        # Add any additional kwargs as context
        for key, value in kwargs.items():
            if not key.startswith('_'):
                context_data[key] = value
        
        if context_data:
            extra['context_data'] = context_data
        
        super()._log(
            level,
            msg,
            args,
            exc_info=exc_info,
            extra=extra,
            stack_info=stack_info
        )
    
    def with_context(
        self,
        **kwargs
    ):
        """Create a logger with context variables set"""
        class ContextualLoggerWrapper:
            def __init__(self, logger, context):
                self.logger = logger
                self.context = context
            
            def log(self, level, msg, *args, **log_kwargs):
                merged_kwargs = {**self.context, **log_kwargs}
                self.logger._log(level, msg, args, **merged_kwargs)
            
            def debug(self, msg, *args, **kwargs):
                self.log(logging.DEBUG, msg, *args, **kwargs)
            
            def info(self, msg, *args, **kwargs):
                self.log(logging.INFO, msg, *args, **kwargs)
            
            def warning(self, msg, *args, **kwargs):
                self.log(logging.WARNING, msg, *args, **kwargs)
            
            def error(self, msg, *args, **kwargs):
                self.log(logging.ERROR, msg, *args, **kwargs)
            
            def critical(self, msg, *args, **kwargs):
                self.log(logging.CRITICAL, msg, *args, **kwargs)
        
        return ContextualLoggerWrapper(self, kwargs)


def setup_structured_logging(log_level=logging.INFO):
    """Setup structured logging for the application"""
    logging.setLoggerClass(ContextualLogger)
    
    # Create formatter
    formatter = StructuredFormatter()
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for request tracking
    
    Returns:
        The correlation ID (generated if not provided)
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    correlation_id_var.set(correlation_id)
    return correlation_id


def set_task_id(task_id: str):
    """Set task ID for logging context"""
    task_id_var.set(task_id)


def set_user_id(user_id: str):
    """Set user ID for logging context"""
    user_id_var.set(user_id)


def clear_context():
    """Clear all context variables"""
    correlation_id_var.set('')
    task_id_var.set('')
    user_id_var.set('')


def get_context() -> Dict[str, str]:
    """Get all context variables
    
    Returns:
        Dict with current context
    """
    return {
        "correlation_id": correlation_id_var.get(),
        "task_id": task_id_var.get(),
        "user_id": user_id_var.get()
    }
