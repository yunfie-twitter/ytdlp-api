# Pydantic v2 Validation Error & Dependency Fixes

## Problem Summary

### Issue #1: Pydantic v2 Validation Error

When running the application with Docker Compose, a Pydantic validation error was thrown:

```
pydantic_core._pydantic_core.ValidationError: 24 validation errors for Settings
RELOAD
  Extra inputs are not permitted [type=extra_forbidden, input_value='false', input_type=str]
ENABLE_JWT_AUTH
  Extra inputs are not permitted [type=extra_forbidden, input_value='false', input_type=str]
...
```

### Issue #2: Missing PyJWT Dependency

After fixing the Pydantic validation error, the following error occurred:

```
ModuleNotFoundError: No module named 'jwt'
  File "/app/core/auth/jwt_auth.py", line 6, in <module>
    import jwt
```

### Issue #3: Invalid yt-dlp-ejs Version

Docker build failed with:

```
ERROR: Could not find a version that satisfies the requirement yt-dlp-ejs>=1.0.0
(from versions: 0.1.0, 0.2.0, 0.2.1, 0.3.0, 0.3.1, 0.3.2)
ERROR: No matching distribution found for yt-dlp-ejs>=1.0.0
```

The latest available version is `0.3.2`, but the requirement was set to `>=1.0.0`.

## Root Causes

### Cause #1: Pydantic v2 Default Behavior Change

In **Pydantic v2**, the default behavior changed:
- **Pydantic v1**: Extra fields were ignored by default
- **Pydantic v2**: Extra fields are now forbidden by default when using `BaseSettings`

### Cause #2: Incomplete Dependency List

The `requirements.txt` was missing `PyJWT`, which is required by the JWT authentication module.

### Cause #3: Incorrect Version Specification

The `yt-dlp-ejs` package requirement was set to `>=1.0.0`, but the package only has versions up to `0.3.2` released on PyPI.

### Cause #4: Inflexible Version Pinning

The original `requirements.txt` used strict `==` version pinning, which prevents compatible security updates.

## Solutions Applied

### Fix #1: Updated `core/config/settings.py`

Updated to use Pydantic v2's `ConfigDict` with `extra='ignore'`:

```python
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
```

### Fix #2: Added Missing PyJWT Dependency

Added `PyJWT>=2.8.1` to `requirements.txt`

### Fix #3: Corrected yt-dlp-ejs Version

Updated from `yt-dlp-ejs>=1.0.0` to `yt-dlp-ejs>=0.3.0`

### Fix #4: Refactored `requirements.txt` with Flexible Version Pinning

Converted all dependencies from strict `==` to flexible `>=` format

## Deployment Steps

1. **Pull the latest changes**
   ```bash
   git checkout fix/pydantic-v2-validation
   git pull origin fix/pydantic-v2-validation
   ```

2. **Rebuild Docker image**
   ```bash
   docker-compose down -v
   docker-compose up -d --build
   ```

3. **Verify the application**
   ```bash
   docker-compose logs -f ytdlp-api
   ```

---

**Status**: ✅ Fixed and ready for production
**Last Updated**: 2025-12-11
