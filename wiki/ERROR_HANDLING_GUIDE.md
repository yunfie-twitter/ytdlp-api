"""ERROR_HANDLING_GUIDE.md content - moved from root to wiki folder"""
# Error Handling Guide

## Overview

This guide explains the comprehensive error handling system in ytdlp-api v1.0.7+, which provides robust error recovery, automatic retries, and detailed error reporting.

## Error Types

### 1. **ValidationError** 🔍
Occurs when input validation fails

```python
from core.error_handler import ValidationError

try:
    if not url:
        raise ValidationError("URL is required")
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
```

### 2. **NetworkError** 🌐
Occurs during network communication failures

```python
from core.error_handler import NetworkError

try:
    response = await fetch_with_retry(url)
except NetworkError as e:
    logger.error(f"Network error: {e}")
```

### 3. **DatabaseError** 💾
Occurs during database operations

```python
from core.error_handler import DatabaseError

try:
    await db.execute(query)
except DatabaseError as e:
    logger.error(f"Database error: {e}")
```

### 4. **TimeoutError** ⏱️
Occurs when operations exceed timeout limits

```python
from core.error_handler import TimeoutError

try:
    await asyncio.wait_for(operation(), timeout=30)
except TimeoutError as e:
    logger.error(f"Timeout: {e}")
```

## Error Context Management

Use ErrorContext to track error context:

```python
from core.error_handler import ErrorContext

with ErrorContext("download_task", task_id=task_id, url=url):
    await download_service.download(url)
```

## Retry Strategy

Automatic retry with exponential backoff:

```python
from core.error_handler import retry

@retry(
    max_attempts=3,
    backoff=1.0,
    backoff_multiplier=2.0,
    exceptions=(ConnectionError, TimeoutError)
)
async def download_with_retry(url: str):
    return await download_service.download(url)
```

## Circuit Breaker Pattern

Prevent cascading failures:

```python
from core.error_handler import CircuitBreaker

circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60
)

with circuit_breaker:
    await risky_operation()
```

## Best Practices

1. **Always use ErrorContext** for operation tracking
2. **Specific exception types** for different scenarios
3. **Logging at appropriate levels** (debug, info, warning, error)
4. **Resource cleanup** with try-finally blocks
5. **Meaningful error messages** for debugging

## Example: Complete Error Handling

```python
from core.error_handler import ErrorContext, ValidationError, retry

@retry(max_attempts=3)
async def download_task(task_id: str, url: str):
    with ErrorContext("download", task_id=task_id):
        # Validation
        if not url:
            raise ValidationError("URL required")
        
        try:
            # Operation
            result = await download_service.download(url)
            logger.info(f"Download completed: {task_id}")
            return result
        
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise
        
        finally:
            # Cleanup
            await cleanup_resources(task_id)
```
