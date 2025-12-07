"""PROJECT_STRUCTURE.md content - moved from root to wiki folder"""
# Project Structure

## Directory Layout

```
ytdlp-api/
├── app/                          # FastAPI application
│   ├── __init__.py
│   ├── main.py                   # Application factory
│   ├── endpoints.py              # API endpoints
│   ├── auth_endpoints.py         # Authentication endpoints
│   ├── progress_endpoints.py     # Progress tracking endpoints
│   ├── metrics_endpoints.py      # Metrics endpoints
│   ├── performance_endpoints.py  # Performance monitoring
│   └── error_responses.py        # Error handling
│
├── core/                         # Core utilities
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── security.py               # Security utilities
│   ├── jwt_auth.py               # JWT authentication
│   ├── error_handler.py          # Error handling system
│   ├── cache_manager.py          # Caching system
│   ├── rate_limiter.py           # Rate limiting
│   ├── monitoring.py             # Health monitoring
│   ├── performance.py            # Performance optimization
│   ├── code_quality.py           # Code quality analysis
│   ├── database_optimization.py  # Database optimization
│   ├── logging_config.py         # Logging configuration
│   └── logging_middleware.py     # Logging middleware
│
├── services/                     # Business logic
│   ├── __init__.py
│   ├── download_service.py       # Download management
│   ├── queue_worker.py           # Queue worker
│   ├── job_manager.py            # Job management
│   ├── circuit_breaker.py        # Circuit breaker pattern
│   └── ffmpeg_service.py         # FFmpeg wrapper
│
├── infrastructure/               # External services
│   ├── __init__.py
│   ├── database.py               # Database connection
│   ├── redis_manager.py          # Redis connection
│   └── resource_pool.py          # Resource pool management
│
├── examples/                     # Example files
│   └── [example scripts]
│
├── wiki/                         # Documentation
│   ├── ERROR_HANDLING_GUIDE.md
│   ├── IMPROVEMENTS.md
│   ├── JWT_AND_FEATURES_GUIDE.md
│   ├── PROGRESS_TRACKING_GUIDE.md
│   ├── PROJECT_STRUCTURE.md
│   └── STABILIZATION_AND_OPTIMIZATION_GUIDE.md
│
├── logs/                         # Log files
├── temp/                         # Temporary files
├── downloads/                    # Downloaded files
│
├── docker-compose.yml            # Docker composition
├── Dockerfile                    # Docker build
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── CHANGELOG.md                  # Version history
├── README.md                     # Quick start
├── LICENSE                       # MIT License
└── main.py                       # Entry point
```

## Key Files

### `app/main.py`
FastAPI application factory with startup/shutdown events

### `core/config.py`
Centralized configuration management using Pydantic

### `services/download_service.py`
Main download service using yt-dlp

### `services/queue_worker.py`
Asynchronous queue worker for processing downloads

### `infrastructure/database.py`
SQLAlchemy database connection and session management

### `infrastructure/redis_manager.py`
Redis connection and operations wrapper

## Module Dependencies

```
app/
  ├─> core/
  ├─> services/
  └─> infrastructure/

services/
  ├─> core/
  └─> infrastructure/

infrastructure/
  └─> core/
```

## Configuration Files

### `.env`
Environment variables (created from `.env.example`)

```bash
DATABASE_URL=postgresql://user:pass@localhost/dbname
REDIS_URL=redis://localhost:6379
ENABLE_JWT_AUTH=true
JWT_SECRET=your-secret-key
```

### `docker-compose.yml`
Docker services (PostgreSQL, Redis)

### `requirements.txt`
Python package dependencies

## Startup Sequence

1. Load `.env` configuration
2. Initialize database connection
3. Connect to Redis
4. Start queue worker
5. Initialize FastAPI app
6. Register API routes
7. Start Uvicorn server

## File Organization Best Practices

1. **One responsibility per module**
2. **Core utilities in `core/`**
3. **Business logic in `services/`**
4. **External integrations in `infrastructure/`**
5. **API routes in `app/`**
6. **Keep functions small and focused**
7. **Use type hints throughout**
8. **Document public APIs**

