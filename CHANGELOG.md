# Changelog

All notable changes to this project will be documented in this file.

## [1.0.3] - 2025-12-07

### Added ✨
- Input validation helpers: `_is_valid_url()`, `_is_valid_uuid()`, `_is_valid_language_code()`
- Enhanced logging format with timestamp and logger name
- `get_queue_length()` method to Redis manager
- Graceful degradation for Redis connection failures
- Resource cleanup for temporary subtitle files
- Health check endpoint response timestamp
- API documentation endpoints: `/api/docs` and `/api/openapi.json`
- Comprehensive error handling for timeout scenarios (408 status code)
- Startup/shutdown sequence logging

### Improved 🚀
- Input validation on all API endpoints (URL format, UUID format, language codes, format whitelist)
- Error handling with specific HTTP status codes for different error types
- Resource cleanup with try-finally blocks to prevent memory leaks
- Logging granularity and readability
- CORS configuration with origin whitespace stripping and max_age directive
- Rate limiting resilience with graceful degradation
- Download service initialization logging
- GPU encoder detection and logging
- Health check response structure
- Process management in download service

### Fixed 🐛
- Potential memory leaks from unclosed processes
- Missing error handling for asyncio timeout scenarios
- Inconsistent error messages
- Incomplete resource cleanup in exception paths
- Missing queue length endpoint

### Security 🔒
- Added URL validation to prevent injection attacks
- Added UUID validation to prevent unauthorized task access
- Enhanced input sanitization for all parameters

## [1.0.2] - 2025-12-07

### Added ✨
- Complete project restructuring with organized package layout
- `app/` package for FastAPI application
- `core/` package for configuration and security
- `services/` package for business logic
- `infrastructure/` package for external services
- PROJECT_STRUCTURE.md documentation
- Package initialization files with module docstrings

### Changed 📝
- Moved all service files to appropriate packages
- Reorganized imports throughout the project
- Created unified configuration management in `core/config.py`
- Separated security concerns into `core/security.py`

### Removed 🗑️
- Duplicate root-level files (database.py, download_service.py, etc.)
- Merged rate_limiter.py into core/security.py

## [1.0.1] - Initial Release

### Features
- Full-featured video/audio download API using yt-dlp
- Support for multiple formats (MP3, MP4, WebM, WAV, FLAC, AAC)
- Queue management with configurable concurrent downloads
- Real-time progress updates via WebSocket
- Polling-based status endpoint
- Rate limiting by IP address
- MP3 ID3 tag embedding
- Thumbnail embedding in audio files
- Subtitle download capability
- GPU encoding support (NVIDIA NVENC, AMD VAAPI, Intel QSV)
- Aria2 external downloader support
- Redis-based queue management
- SQLAlchemy ORM for task persistence
- Docker support with Dockerfile and docker-compose.yml
- Comprehensive error handling and logging

---

## Migration Guide

### From v1.0.1 to v1.0.3

#### 1. Update imports in existing code:
```python
# Old
from config import settings
from database import get_db
from download_service import download_service

# New
from core.config import settings
from infrastructure.database import get_db
from services.download_service import download_service
```

#### 2. Ensure Docker image is rebuilt:
```bash
docker build -t ytdlp-api:1.0.3 .
```

#### 3. New input validation
Clients must now:
- Send valid HTTP/HTTPS URLs
- Use valid UUID format for task IDs
- Use valid language codes (e.g., en, ja, en-US)
- Use only supported format types

#### 4. Benefits
- Better error messages for invalid input
- Improved error handling and timeout management
- Enhanced logging for debugging
- Better resource cleanup

---

## Breaking Changes

### v1.0.3
- Invalid input (malformed URLs, invalid UUIDs, invalid formats) now properly rejected with specific error messages
- Timeout errors now return 408 status code instead of 400

### v1.0.2
- Complete restructuring of package layout - all imports changed
- Applications using v1.0.1 will require import updates

---

## Known Issues

- None currently reported

---

## Future Roadmap

### Planned for v1.1.0
- [ ] OAuth2 authentication
- [ ] Download history per user
- [ ] Batch download support
- [ ] Custom output filename patterns
- [ ] Webhook notifications on task completion
- [ ] Advanced analytics dashboard
- [ ] Download templates/presets
- [ ] Video preview generation

### Under Consideration
- [ ] Stream from cloud storage (S3, MinIO)
- [ ] Direct upload after download
- [ ] Video transcoding options
- [ ] Distributed downloading across multiple instances
- [ ] Mobile app API

---

## Contributing

Contributions are welcome! Please ensure:
1. Code follows the existing style
2. All imports use the new package structure
3. Error handling is comprehensive
4. Logging is appropriate
5. Tests are included for new features

---

## License

MIT License - See LICENSE file for details
