# Pydantic v2 Validation Error Fix

## Problem Summary

When running the application with Docker Compose, a Pydantic validation error was thrown:

```
pydantic_core._pydantic_core.ValidationError: 24 validation errors for Settings
RELOAD
  Extra inputs are not permitted [type=extra_forbidden, input_value='false', input_type=str]
ENABLE_JWT_AUTH
  Extra inputs are not permitted [type=extra_forbidden, input_value='false', input_type=str]
...
```

## Root Cause

The `.env` file contained environment variables that were not defined in the `Settings` class in `core/config/settings.py`. 

In **Pydantic v2**, the default behavior changed:
- **Pydantic v1**: Extra fields were ignored by default
- **Pydantic v2**: Extra fields are now forbidden by default when using `BaseSettings`

This means any environment variable in the `.env` file that is not defined in the `Settings` class will cause a validation error.

## Solution Applied

Updated `core/config/settings.py` to use Pydantic v2's `ConfigDict` with `extra='ignore'`:

```python
from pydantic import ConfigDict

class Settings(BaseSettings):
    # ... field definitions ...
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra environment variables not defined in the model
    )
```

### Key Changes:

1. **Replaced old `Config` class** with **Pydantic v2's `ConfigDict`**
   - Old: `class Config: env_file = ".env"`
   - New: `model_config = ConfigDict(env_file=".env", extra="ignore")`

2. **Added import**: `from pydantic import ConfigDict`

3. **Set `extra='ignore'`**: This tells Pydantic to silently ignore any environment variables that are not defined in the `Settings` class

## Benefits

- ✅ Allows `.env` to contain extra variables without breaking
- ✅ Maintains backward compatibility with existing `.env` files
- ✅ More flexible configuration management
- ✅ Prevents errors from optional or legacy environment variables

## Deployment Steps

1. Merge this branch into `main`
2. Rebuild Docker image: `docker-compose up -d --build`
3. The application should now start without validation errors

## Testing

The fix can be tested by:

1. Creating a `.env` file from `.env.example`
2. Running `docker-compose up -d`
3. Checking logs: `docker-compose logs ytdlp-api`
4. API should be accessible at `http://localhost:8000`
5. Swagger docs at `http://localhost:8000/docs`

## Related Issues

- Pydantic v2 Migration Guide: https://docs.pydantic.dev/latest/api/config/#configdict
- BaseSettings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
