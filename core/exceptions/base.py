"""Custom exception classes for the application"""
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class APIException(Exception):
    """Base exception for API errors"""
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response"""
        return {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details
        }

# Input Validation Errors
class ValidationError(APIException):
    """Raised when input validation fails"""
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
            details=details
        )

class InvalidURLError(ValidationError):
    """Raised when URL format is invalid"""
    def __init__(self, url: str):
        super().__init__(
            message=f"Invalid URL format: {url[:50]}",
            error_code="INVALID_URL"
        )

class InvalidUUIDError(ValidationError):
    """Raised when UUID format is invalid"""
    def __init__(self, uuid_str: str):
        super().__init__(
            message=f"Invalid UUID format: {uuid_str}",
            error_code="INVALID_UUID"
        )

class InvalidFormatError(ValidationError):
    """Raised when format is not supported"""
    def __init__(self, format_type: str, allowed: list):
        super().__init__(
            message=f"Invalid format '{format_type}'. Allowed: {', '.join(allowed)}",
            error_code="INVALID_FORMAT",
            details={"allowed_formats": allowed, "received": format_type}
        )

class InvalidLanguageCodeError(ValidationError):
    """Raised when language code format is invalid"""
    def __init__(self, lang: str):
        super().__init__(
            message=f"Invalid language code: {lang}. Format: en or en-US",
            error_code="INVALID_LANGUAGE_CODE"
        )

# Resource Not Found Errors
class NotFoundError(APIException):
    """Raised when resource is not found"""
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} not found: {resource_id}",
            status_code=404,
            error_code="NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": resource_id}
        )

class TaskNotFoundError(NotFoundError):
    """Raised when task is not found"""
    def __init__(self, task_id: str):
        super().__init__("Task", task_id)

class FileNotFoundError(NotFoundError):
    """Raised when file is not found"""
    def __init__(self, file_path: str):
        super().__init__("File", file_path)

# Download Errors
class DownloadError(APIException):
    """Raised when download fails"""
    def __init__(self, message: str, task_id: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["task_id"] = task_id
        super().__init__(
            message=message,
            status_code=400,
            error_code="DOWNLOAD_ERROR",
            details=details
        )

class DownloadTimeoutError(DownloadError):
    """Raised when download times out"""
    def __init__(self, task_id: str, timeout_seconds: int):
        super().__init__(
            message=f"Download timed out after {timeout_seconds} seconds",
            task_id=task_id,
            details={"timeout_seconds": timeout_seconds}
        )

class VideoInfoError(DownloadError):
    """Raised when video info retrieval fails"""
    def __init__(self, url: str, reason: str, task_id: str = None):
        super().__init__(
            message=f"Failed to retrieve video info: {reason}",
            task_id=task_id or "unknown",
            details={"url": url[:60], "reason": reason}
        )

# Queue Errors
class QueueError(APIException):
    """Raised when queue operation fails"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="QUEUE_ERROR",
            details=details
        )

class TaskNotCancellableError(APIException):
    """Raised when task cannot be cancelled"""
    def __init__(self, task_id: str, status: str):
        super().__init__(
            message=f"Task cannot be cancelled in '{status}' status",
            status_code=400,
            error_code="TASK_NOT_CANCELLABLE",
            details={"task_id": task_id, "status": status}
        )

# External Service Errors
class ExternalServiceError(APIException):
    """Raised when external service fails"""
    def __init__(self, service_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["service"] = service_name
        super().__init__(
            message=f"{service_name} error: {message}",
            status_code=503,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details
        )

class RedisError(ExternalServiceError):
    """Raised when Redis operation fails"""
    def __init__(self, message: str):
        super().__init__("Redis", message)

class DatabaseError(ExternalServiceError):
    """Raised when database operation fails"""
    def __init__(self, message: str, query: str = None):
        details = {}
        if query:
            details["query"] = query[:100]
        super().__init__("Database", message, details)

class YtDlpError(ExternalServiceError):
    """Raised when yt-dlp command fails"""
    def __init__(self, message: str, url: str = None, return_code: int = None):
        details = {}
        if url:
            details["url"] = url[:60]
        if return_code is not None:
            details["return_code"] = return_code
        super().__init__("yt-dlp", message, details)

# Rate Limiting Errors
class RateLimitError(APIException):
    """Raised when rate limit is exceeded"""
    def __init__(self, ip: str, limit: int, window: int):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window} seconds",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"ip": ip, "limit": limit, "window_seconds": window}
        )

# Timeout Errors
class TimeoutError(APIException):
    """Raised when operation times out"""
    def __init__(self, operation: str, timeout_seconds: int):
        super().__init__(
            message=f"{operation} timed out after {timeout_seconds} seconds",
            status_code=408,
            error_code="TIMEOUT",
            details={"operation": operation, "timeout_seconds": timeout_seconds}
        )

# State Errors
class InvalidStateError(APIException):
    """Raised when operation is invalid for current state"""
    def __init__(self, current_state: str, operation: str, allowed_states: list):
        super().__init__(
            message=f"Cannot {operation} in '{current_state}' state",
            status_code=409,
            error_code="INVALID_STATE",
            details={
                "current_state": current_state,
                "operation": operation,
                "allowed_states": allowed_states
            }
        )

# File System Errors
class FileAccessError(APIException):
    """Raised when file access is denied"""
    def __init__(self, file_path: str, reason: str):
        super().__init__(
            message=f"File access denied: {reason}",
            status_code=403,
            error_code="FILE_ACCESS_DENIED",
            details={"file_path": file_path[:100], "reason": reason}
        )

class PathTraversalError(FileAccessError):
    """Raised when path traversal attempt is detected"""
    def __init__(self, file_path: str):
        super().__init__(
            file_path=file_path,
            reason="Path traversal attempt detected"
        )

class DiskSpaceError(APIException):
    """Raised when disk space is insufficient"""
    def __init__(self, required_bytes: int, available_bytes: int):
        super().__init__(
            message="Insufficient disk space",
            status_code=507,
            error_code="INSUFFICIENT_DISK_SPACE",
            details={
                "required_bytes": required_bytes,
                "available_bytes": available_bytes,
                "deficit_bytes": required_bytes - available_bytes
            }
        )

# Conflict Errors
class ConflictError(APIException):
    """Raised when operation conflicts with existing state"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details
        )

# Internal Errors
class InternalServerError(APIException):
    """Raised for unexpected internal errors"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
            details=details
        )
