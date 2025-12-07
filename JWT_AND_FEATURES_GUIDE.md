# JWT Authentication and Feature Flags Guide - ytdlp-api v1.0.5

## Overview

This guide explains the JWT authentication system and feature flags system implemented in ytdlp-api v1.0.5.

---

## Table of Contents

1. [JWT Authentication](#jwt-authentication)
2. [API Key Management](#api-key-management)
3. [Feature Flags](#feature-flags)
4. [Environment Configuration](#environment-configuration)
5. [Usage Examples](#usage-examples)
6. [Security Best Practices](#security-best-practices)

---

## JWT Authentication

### Overview

JWT (JSON Web Token) authentication provides secure API access control. The system works as follows:

1. **Enable JWT Auth**: Set `ENABLE_JWT_AUTH=true` in `.env`
2. **Set Issuance Password**: Set `API_KEY_ISSUE_PASSWORD` in `.env`
3. **Issue API Keys**: Call `/api/auth/issue-key` with password
4. **Use API Key**: Include token in `Authorization: Bearer <token>` header

### Enabling JWT Authentication

```bash
# .env
ENABLE_JWT_AUTH=true
API_KEY_ISSUE_PASSWORD=your-secure-password
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DAYS=30
```

**Configuration Options:**

| Option | Description | Default |
|--------|-------------|----------|
| `ENABLE_JWT_AUTH` | Enable/disable JWT auth system | `false` |
| `API_KEY_ISSUE_PASSWORD` | Password for key issuance (required if JWT enabled) | (none) |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `JWT_EXPIRATION_DAYS` | Token expiration in days | `30` |
| `SECRET_KEY` | Secret key for signing | (must change in production) |

---

## API Key Management

### Issuing API Keys

#### Endpoint

```
POST /api/auth/issue-key
```

#### Request

```json
{
  "password": "your-secure-password",
  "user_id": "optional-user-id",
  "description": "My API Key"
}
```

#### Response

```json
{
  "api_key_id": "abcd1234...",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user_id": "optional-user-id",
  "description": "My API Key",
  "message": "API key issued successfully. Use token in Authorization header: Bearer <token>"
}
```

#### Example

```bash
curl -X POST http://localhost:8000/api/auth/issue-key \
  -H "Content-Type: application/json" \
  -d '{
    "password": "your-secure-password",
    "user_id": "user123",
    "description": "Production API Key"
  }'
```

### Using API Keys

Include the token in the `Authorization` header:

```bash
curl -X GET http://localhost:8000/api/info?url=https://example.com \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

Or in Python:

```python
import requests

token = "eyJhbGciOiJIUzI1NiIs..."
headers = {"Authorization": f"Bearer {token}"}

response = requests.get(
    "http://localhost:8000/api/info",
    params={"url": "https://example.com"},
    headers=headers
)
```

### Listing API Keys

#### Endpoint

```
GET /api/auth/keys?user_id=optional-user-id
Authorization: Bearer <token>
```

#### Response

```json
[
  {
    "api_key_id": "abcd1234...",
    "user_id": "user123",
    "description": "My API Key",
    "created_at": "2025-12-07T10:00:00",
    "last_used": "2025-12-07T15:30:00",
    "active": true
  }
]
```

#### Example

```bash
curl -X GET http://localhost:8000/api/auth/keys \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Revoking API Keys

#### Endpoint

```
POST /api/auth/revoke-key
Authorization: Bearer <token>
```

#### Request

```json
{
  "api_key_id": "abcd1234..."
}
```

#### Example

```bash
curl -X POST http://localhost:8000/api/auth/revoke-key \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"api_key_id": "abcd1234..."}'
```

### Updating API Keys

#### Endpoint

```
PATCH /api/auth/keys/{api_key_id}
Authorization: Bearer <token>
```

#### Request

```json
{
  "description": "Updated description",
  "active": true
}
```

#### Example

```bash
curl -X PATCH http://localhost:8000/api/auth/keys/abcd1234 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"description": "Updated description"}'
```

### Checking Auth Status

#### Endpoint

```
GET /api/auth/status
```

#### Response

```json
{
  "jwt_enabled": true,
  "api_key_issuance_enabled": true,
  "algorithm": "HS256",
  "expiration_days": 30
}
```

---

## Feature Flags

Feature flags allow you to enable/disable specific features without redeploying the application.

### Available Features

| Feature | Flag | Description |
|---------|------|-------------|
| Video Info | `ENABLE_FEATURE_VIDEO_INFO` | Get video info endpoint |
| Download | `ENABLE_FEATURE_DOWNLOAD` | Create downloads |
| Status | `ENABLE_FEATURE_STATUS` | Check task status |
| File Download | `ENABLE_FEATURE_FILE_DOWNLOAD` | Download completed files |
| Cancel | `ENABLE_FEATURE_CANCEL` | Cancel tasks |
| Delete | `ENABLE_FEATURE_DELETE` | Delete tasks |
| List Tasks | `ENABLE_FEATURE_LIST_TASKS` | List all tasks |
| Subtitles | `ENABLE_FEATURE_SUBTITLES` | Download subtitles |
| Thumbnail | `ENABLE_FEATURE_THUMBNAIL` | Get thumbnails |
| Queue Stats | `ENABLE_FEATURE_QUEUE_STATS` | Get queue statistics |
| WebSocket | `ENABLE_FEATURE_WEBSOCKET` | Real-time updates |
| MP3 Metadata | `ENABLE_FEATURE_MP3_METADATA` | ID3 tag embedding |
| Thumbnail Embed | `ENABLE_FEATURE_THUMBNAIL_EMBED` | Embed in audio |
| GPU Encoding | `ENABLE_FEATURE_GPU_ENCODING` | GPU support |
| Aria2 | `ENABLE_FEATURE_ARIA2` | Aria2 downloader |
| Custom Format | `ENABLE_FEATURE_CUSTOM_FORMAT` | Custom formats |
| Quality | `ENABLE_FEATURE_QUALITY_SELECTION` | Quality selection |
| Proxy | `ENABLE_FEATURE_PROXY` | Proxy support |
| Cookies | `ENABLE_FEATURE_COOKIES` | Cookie support |

### Disabling Features

Edit `.env` to disable features:

```bash
# Disable video info endpoint
ENABLE_FEATURE_VIDEO_INFO=false

# Disable download creation
ENABLE_FEATURE_DOWNLOAD=false

# Disable subtitles
ENABLE_FEATURE_SUBTITLES=false
```

### Checking Enabled Features

#### Endpoint

```
GET /api/features
```

#### Response

```json
{
  "video_info": true,
  "download": true,
  "status": true,
  "file_download": true,
  "cancel": true,
  "delete": true,
  "list_tasks": true,
  "subtitles": true,
  "thumbnail": true,
  "queue_stats": true,
  "websocket": true,
  "mp3_metadata": true,
  "thumbnail_embed": true,
  "gpu_encoding": true,
  "aria2": true,
  "custom_format": true,
  "quality_selection": true,
  "proxy": true,
  "cookies": true
}
```

---

## Environment Configuration

### Complete Configuration Example

```bash
# Production setup with JWT auth enabled

# API
HOST=0.0.0.0
PORT=8000

# Security
SECRET_KEY=your-super-secret-key-that-is-very-long
ENABLE_JWT_AUTH=true
API_KEY_ISSUE_PASSWORD=secure-password-123
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DAYS=30

# CORS
CORS_ORIGINS=https://app.example.com,https://api.example.com

# Database
DATABASE_URL=postgresql://user:pass@localhost/ytdlp

# Redis
REDIS_URL=redis://localhost:6379

# Download
DOWNLOAD_DIR=/var/downloads
MAX_CONCURRENT_DOWNLOADS=5

# Features
ENABLE_FEATURE_VIDEO_INFO=true
ENABLE_FEATURE_DOWNLOAD=true
ENABLE_FEATURE_SUBTITLES=true
ENABLE_FEATURE_GPU_ENCODING=true
ENABLE_FEATURE_ARIA2=true

# GPU
ENABLE_GPU_ENCODING=true
GPU_ENCODER_TYPE=nvenc
GPU_ENCODER_PRESET=fast
```

---

## Usage Examples

### Example 1: Basic Setup

```bash
# .env
ENABLE_JWT_AUTH=true
API_KEY_ISSUE_PASSWORD=my-password

# Start server
python -m uvicorn app.main:app --reload

# Issue API key
curl -X POST http://localhost:8000/api/auth/issue-key \
  -H "Content-Type: application/json" \
  -d '{"password": "my-password"}'

# Use API key to download
curl -X POST http://localhost:8000/api/download \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.mp4", "format": "mp4"}'
```

### Example 2: Disable Specific Features

```bash
# .env - read-only API
ENABLE_FEATURE_DOWNLOAD=false
ENABLE_FEATURE_CANCEL=false
ENABLE_FEATURE_DELETE=false

# Users can only get info and status
# Download/cancel/delete return 403 Forbidden
```

### Example 3: Public API with Auth

```bash
# .env - public server with optional auth
ENABLE_JWT_AUTH=true
API_KEY_ISSUE_PASSWORD=public-key-password

# All endpoints work without auth (optional)
# Authenticated users can access restricted features
```

---

## Security Best Practices

### 1. Change Secret Key in Production

```bash
# Generate random secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Use in .env
SECRET_KEY=your-generated-secret-key
```

### 2. Use Strong API Key Issuance Password

```bash
# Generate strong password
openssl rand -base64 32

# Use in .env
API_KEY_ISSUE_PASSWORD=your-strong-password
```

### 3. Rotate API Keys

- Issue new keys for critical operations
- Revoke old keys after rotation period
- Monitor `last_used` timestamp

### 4. Restrict CORS Origins

```bash
# .env - only allow specific domains
CORS_ORIGINS=https://trusted-app.com,https://api.trusted.com
```

### 5. Use HTTPS in Production

```bash
# Always use HTTPS for API endpoints
# Never send API keys over HTTP
https://api.example.com/api/auth/issue-key
```

### 6. Set Appropriate Expiration

```bash
# Balance security and convenience
JWT_EXPIRATION_DAYS=7   # Very secure
JWT_EXPIRATION_DAYS=90  # Standard
JWT_EXPIRATION_DAYS=365 # Long-lived
```

### 7. Implement Rate Limiting

```bash
# Limit password attempts
# Log failed attempts
# Alert on suspicious activity
RATE_LIMIT_PER_MINUTE=60
```

---

## Troubleshooting

### Issue: "JWT authentication is disabled"

**Solution**: Set `ENABLE_JWT_AUTH=true` in `.env`

### Issue: "API key issuance is disabled"

**Solution**: Set `API_KEY_ISSUE_PASSWORD` in `.env`

### Issue: "Invalid password"

**Solution**: Check that the password matches `API_KEY_ISSUE_PASSWORD` exactly

### Issue: "Token has expired"

**Solution**: Issue a new API key

### Issue: "Feature is disabled"

**Solution**: Set the feature flag to `true` in `.env` and restart the application

---

## API Reference

### Authentication Endpoints

| Method | Path | Authentication | Description |
|--------|------|-----------------|-------------|
| POST | `/api/auth/issue-key` | No | Issue new API key |
| GET | `/api/auth/status` | No | Check auth status |
| GET | `/api/auth/keys` | Required | List API keys |
| POST | `/api/auth/revoke-key` | Required | Revoke API key |
| PATCH | `/api/auth/keys/{id}` | Required | Update API key |

### Features Endpoint

| Method | Path | Authentication | Description |
|--------|------|-----------------|-------------|
| GET | `/api/features` | No | List feature status |

---

**Last Updated**: 2025-12-07  
**Version**: 1.0.5  
**Status**: Production Ready ✅
