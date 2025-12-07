# Error Handling Guide - ytdlp-api v1.0.4

## 🎯 Overview

This guide explains the comprehensive error handling system implemented in ytdlp-api v1.0.4.

---

## Exception Hierarchy

```
APIException (Base)
├─ ValidationError (400)
│  ├─ InvalidURLError
│  ├─ InvalidUUIDError
│  ├─ InvalidFormatError
│  └─ InvalidLanguageCodeError
├─ NotFoundError (404)
│  ├─ TaskNotFoundError
│  └─ FileNotFoundError
├─ DownloadError (400)
│  ├─ DownloadTimeoutError
│  └─ VideoInfoError
├─ QueueError (500)
│  └─ TaskNotCancellableError
├─ ExternalServiceError (503)
│  ├─ RedisError
│  ├─ DatabaseError
│  └─ YtDlpError
├─ RateLimitError (429)
├─ TimeoutError (408)
├─ InvalidStateError (409)
├─ FileAccessError (403)
│  ├─ PathTraversalError
│  └─ DiskSpaceError
├─ ConflictError (409)
└─ InternalServerError (500)
```

---

## Using Custom Exceptions

### 1. Basic Exception Raising

```python
from core.exceptions import InvalidURLError, TaskNotFoundError

# URL validation
try:
    url = InputValidator.validate_info_request(url)
except InvalidURLError as e:
    # Handled automatically by FastAPI exception handler
    logger.warning(f"Invalid URL: {e}")
    raise

# Task lookup
task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
if not task:
    raise TaskNotFoundError(task_id)
```

### 2. Error Context Manager

```python
from core.error_handler import ErrorContext

# Automatic logging with context
with ErrorContext("get_video_info", task_id=task_id):
    info = await download_service.get_video_info(url)
    # Errors are automatically logged with task_id
```

### 3. Async Error Handler Decorator

```python
from core.error_handler import async_error_handler

@async_error_handler(
    "process_download",
    default_return=None,
    log_errors=True,
    raise_exception=True
)
async def process_download(task_id: str):
    # Errors are automatically caught, logged, and converted to exceptions
    return await download_service.download(task_id)
```

### 4. Sync Error Handler Decorator

```python
from core.error_handler import sync_error_handler

@sync_error_handler(
    "process_data",
    default_return={},
    log_errors=True,
    raise_exception=False
)
def process_data(data):
    # If raise_exception=False, returns default_return on error
    return process_impl(data)
```

---

## Input Validation

### URLValidator

```python
from core.validation import URLValidator, InvalidURLError

# Method 1: Check validation
if URLValidator.validate(url):
    # Valid URL
    pass

# Method 2: Validate and raise
try:
    url = URLValidator.validate_or_raise(url)
except InvalidURLError as e:
    print(f"Invalid URL: {e.message}")
```

### UUIDValidator

```python
from core.validation import UUIDValidator, InvalidUUIDError

# Validate task ID
try:
    task_id = UUIDValidator.validate_or_raise(task_id)
except InvalidUUIDError:
    # Return 400 error
    raise HTTPException(status_code=400)
```

### FormatValidator

```python
from core.validation import FormatValidator, InvalidFormatError

# Check allowed formats
allowed = FormatValidator.get_descriptions()
# Output: {'mp3': 'MP3 Audio', 'mp4': 'MP4 Video', ...}

# Validate format
try:
    format_type = FormatValidator.validate_or_raise(format_type)
except InvalidFormatError as e:
    print(f"Invalid format. Allowed: {e.details['allowed_formats']}")
```

### LanguageCodeValidator

```python
from core.validation import LanguageCodeValidator, InvalidLanguageCodeError

# Validate language code
try:
    lang = LanguageCodeValidator.validate_or_raise(lang)
except InvalidLanguageCodeError:
    # Return 400 error
    raise
```

### Combined InputValidator

```python
from core.validation import InputValidator

# Validate all download parameters at once
try:
    url, format_type, quality = InputValidator.validate_download_request(
        url=request.url,
        format_type=request.format,
        quality=request.quality,
        mp3_title=request.mp3_title
    )
except ValidationError as e:
    # Returns 400 with detailed error information
    raise
```

---

## Error Response Format

### Success Case

```json
HTTP/1.1 200 OK
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "queue_position": 3,
  "message": "Task created and added to queue"
}
```

### Validation Error

```json
HTTP/1.1 400 Bad Request
{
  "error": "INVALID_FORMAT",
  "message": "Invalid format 'xyz'. Allowed: mp3, mp4, best, audio, video, webm, wav, flac, aac",
  "status_code": 400,
  "details": {
    "allowed_formats": ["mp3", "mp4", ...],
    "received": "xyz"
  }
}
```

### Not Found Error

```json
HTTP/1.1 404 Not Found
{
  "error": "NOT_FOUND",
  "message": "Task not found: 123e4567-e89b-12d3-a456-426614174000",
  "status_code": 404,
  "details": {
    "resource_type": "Task",
    "resource_id": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

### Timeout Error

```json
HTTP/1.1 408 Request Timeout
{
  "error": "TIMEOUT",
  "message": "get_video_info timed out after 30 seconds",
  "status_code": 408,
  "details": {
    "operation": "get_video_info",
    "timeout_seconds": 30
  }
}
```

### Rate Limit Error

```json
HTTP/1.1 429 Too Many Requests
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded: 60 requests per 60 seconds",
  "status_code": 429,
  "details": {
    "ip": "192.168.1.1",
    "limit": 60,
    "window_seconds": 60
  }
}
```

### Invalid State Error

```json
HTTP/1.1 409 Conflict
{
  "error": "INVALID_STATE",
  "message": "Cannot cancel in 'completed' state",
  "status_code": 409,
  "details": {
    "current_state": "completed",
    "operation": "cancel",
    "allowed_states": ["pending", "downloading"]
  }
}
```

### Path Traversal Error

```json
HTTP/1.1 403 Forbidden
{
  "error": "FILE_ACCESS_DENIED",
  "message": "File access denied: Path traversal attempt detected",
  "status_code": 403,
  "details": {
    "file_path": "/path/to/../../etc/passwd",
    "reason": "Path traversal attempt detected"
  }
}
```

### Internal Server Error

```json
HTTP/1.1 500 Internal Server Error
{
  "error": "INTERNAL_SERVER_ERROR",
  "message": "An unexpected error occurred: ConnectionError",
  "status_code": 500,
  "details": {
    "path": "/api/download",
    "method": "POST"
  }
}
```

---

## Retry Logic

### Configuration

```python
from core.error_handler import RetryConfig

config = RetryConfig(
    max_attempts=3,           # Retry up to 3 times
    initial_delay=1.0,        # Start with 1 second delay
    backoff_factor=2.0,       # Double the delay each retry
    max_delay=60.0            # Cap at 60 seconds
)

# Retry sequence: 1s, 2s, 4s (total 7s max)
```

### Async Retry

```python
from core.error_handler import async_retry, RetryConfig

config = RetryConfig(max_attempts=3)

try:
    result = await async_retry(
        download_service.get_video_info,
        url,
        config=config,
        retriable_exceptions=(ConnectionError, TimeoutError)
    )
except ConnectionError:
    # All retries failed
    logger.error("Failed to get video info after 3 attempts")
```

### Sync Retry

```python
from core.error_handler import sync_retry

result = sync_retry(
    database.query,
    query_string,
    config=config,
    retriable_exceptions=(sqlite3.OperationalError,)
)
```

---

## Logging Error Information

### Error Summary

```python
from core.error_handler import log_error_summary

try:
    process_data(data)
except Exception as e:
    error_summary = log_error_summary(e, "data_processing")
    logger.error(error_summary)
    # Output:
    # Error in data_processing
    # Type: ValueError
    # Message: Invalid value
    # Status Code: 400 (if APIException)
    # Details: {...}
    # Traceback: ...
```

### ErrorContext Manager

```python
from core.error_handler import ErrorContext

with ErrorContext("download_video", task_id=task_id, log_level=logging.WARNING):
    try:
        await download_service.download(task_id)
    except APIException as e:
        # Logged as WARNING
        raise
    except Exception as e:
        # Logged as ERROR with full traceback
        raise
```

---

## Best Practices

### 1. Use Specific Exceptions

✅ **Good**
```python
if not URLValidator.validate(url):
    raise InvalidURLError(url)

if not task:
    raise TaskNotFoundError(task_id)
```

❌ **Bad**
```python
if not url:
    raise Exception("Invalid URL")

if not task:
    raise ValueError("Task not found")
```

### 2. Provide Context

✅ **Good**
```python
with ErrorContext("process_download", task_id=task_id):
    await download(task_id)
```

❌ **Bad**
```python
await download(task_id)  # No context
```

### 3. Use Error Handlers for Async Functions

✅ **Good**
```python
@async_error_handler("get_info")
async def get_info(url: str):
    return await service.get_info(url)
```

❌ **Bad**
```python
async def get_info(url: str):
    try:
        return await service.get_info(url)
    except Exception as e:
        logger.error(f"Error: {e}")  # Incomplete error handling
```

### 4. Handle Timeouts Explicitly

✅ **Good**
```python
try:
    result = await asyncio.wait_for(operation(), timeout=30)
except asyncio.TimeoutError:
    raise TimeoutError("operation", 30)
```

❌ **Bad**
```python
result = await operation()  # No timeout protection
```

### 5. Validate Input Early

✅ **Good**
```python
@router.post("/download")
async def create_download(request: DownloadRequest):
    url, format_type, quality = InputValidator.validate_download_request(...)
    # Rest of implementation
```

❌ **Bad**
```python
@router.post("/download")
async def create_download(request: DownloadRequest):
    # Use request.url without validation
    await download(request.url)  # May fail later
```

### 6. Log with Appropriate Levels

✅ **Good**
```python
logger.info(f"Task started: {task_id}")
logger.warning(f"Timeout detected: {task_id}")
logger.error(f"Download failed: {task_id}", exc_info=True)
logger.critical(f"Database connection lost")
```

❌ **Bad**
```python
logger.error(f"Task started: {task_id}")  # Wrong level
logger.info(f"Error: {error}")  # Should be error
```

---

## Error Handling Checklist

When implementing a new endpoint or function:

- [ ] Validate all inputs using InputValidator or specific validators
- [ ] Use ErrorContext or @async_error_handler for async operations
- [ ] Handle asyncio.TimeoutError explicitly
- [ ] Check for resource existence before accessing
- [ ] Validate state transitions before operations
- [ ] Perform security checks (path traversal, SQL injection)
- [ ] Log errors with appropriate context and level
- [ ] Return consistent error response format
- [ ] Document error cases in docstring
- [ ] Test error scenarios in unit tests

---

## Common Error Scenarios

### Scenario 1: Invalid URL in Download Request

```python
# User sends invalid URL
POST /api/download
{"url": "not-a-url", "format": "mp3"}

# Handler validates input
url = InputValidator.validate_download_request(url, ...)
# Raises InvalidURLError

# FastAPI converts to JSON response
HTTP/1.1 400 Bad Request
{
  "error": "INVALID_URL",
  "message": "Invalid URL format: not-a-url",
  "status_code": 400,
  "details": {}
}
```

### Scenario 2: Task Already Completed

```python
# User tries to cancel completed task
POST /api/cancel/abc123

# Handler checks state
if task.status != "pending" and task.status != "downloading":
    raise InvalidStateError(
        current_state="completed",
        operation="cancel",
        allowed_states=["pending", "downloading"]
    )

# FastAPI converts to JSON response
HTTP/1.1 409 Conflict
{
  "error": "INVALID_STATE",
  "message": "Cannot cancel in 'completed' state",
  "status_code": 409,
  ...
}
```

### Scenario 3: Redis Failure with Graceful Degradation

```python
# Redis connection fails
try:
    rate_limit_ok = await redis_manager.check_rate_limit(ip)
except RedisError as e:
    logger.error(f"Redis error: {e}")
    # Graceful degradation: allow request
    rate_limit_ok = True

# Request continues normally
```

---

## Testing Error Handling

```bash
# Test invalid URL
curl -X POST http://localhost:8000/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "invalid", "format": "mp3"}'

# Test invalid task ID
curl http://localhost:8000/api/status/not-a-uuid

# Test invalid format
curl -X POST http://localhost:8000/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "format": "xyz"}'

# Test non-existent task
curl http://localhost:8000/api/status/123e4567-e89b-12d3-a456-426614174000

# Test invalid state transition
curl -X POST http://localhost:8000/api/cancel/completed-task-id
```

---

**Last Updated**: 2025-12-07  
**Version**: 1.0.4  
**Status**: Production Ready ✅
