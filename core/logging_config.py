"""Advanced logging configuration and utilities"""
import logging
import logging.handlers
import json
from pathlib import Path
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for better parsing"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)

class PerformanceLogger:
    """Track and log performance metrics"""
    
    def __init__(self, name: str = "performance"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
    
    def log_operation(self, operation: str, duration_ms: float, success: bool = True) -> None:
        """Log operation performance"""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            f"Operation {operation}: {duration_ms:.2f}ms"
        )
    
    def log_query(self, query: str, duration_ms: float, rows_affected: int = 0) -> None:
        """Log database query performance"""
        self.logger.info(
            f"Query executed: {duration_ms:.2f}ms, Rows: {rows_affected}"
        )

def setup_logging(log_dir: str = "./logs", json_format: bool = True) -> None:
    """Setup comprehensive logging system"""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        f"{log_dir}/app.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Error log
    error_handler = logging.FileHandler(f"{log_dir}/error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
