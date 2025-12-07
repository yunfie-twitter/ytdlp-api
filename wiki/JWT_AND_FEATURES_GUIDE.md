"""JWT_AND_FEATURES_GUIDE.md content - moved from root to wiki folder"""
# JWT Authentication & Features Guide

## JWT Authentication

### Enable JWT Auth

Set in `.env`:
```bash
ENABLE_JWT_AUTH=true
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

### Generate API Key

```bash
curl -X POST http://localhost:8000/api/auth/generate-key \
  -H "Content-Type: application/json" \
  -d '{
    "password": "admin-password",
    "description": "My API Key"
  }'
```

### Use API Key

Include in request header:
```bash
curl http://localhost:8000/api/download \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Feature Flags

### Configure Features

Set in `.env`:
```bash
ENABLE_FEATURE_VIDEO_INFO=true
ENABLE_FEATURE_DOWNLOAD=true
ENABLE_FEATURE_STATUS=true
ENABLE_FEATURE_FILE_DOWNLOAD=true
ENABLE_FEATURE_CANCEL=true
ENABLE_FEATURE_DELETE=true
ENABLE_FEATURE_LIST_TASKS=true
ENABLE_FEATURE_SUBTITLES=true
ENABLE_FEATURE_THUMBNAIL=true
ENABLE_FEATURE_QUEUE_STATS=true
ENABLE_FEATURE_PROGRESS_TRACKING=true
ENABLE_FEATURE_WEBSOCKET=true
ENABLE_FEATURE_MP3_METADATA=true
ENABLE_FEATURE_THUMBNAIL_EMBED=true
ENABLE_FEATURE_GPU_ENCODING=true
ENABLE_FEATURE_ARIA2=true
ENABLE_FEATURE_CUSTOM_FORMAT=true
ENABLE_FEATURE_QUALITY_SELECTION=true
ENABLE_FEATURE_PROXY=true
ENABLE_FEATURE_COOKIES=true
ENABLE_FEATURE_METRICS=true
```

### Check Feature Status

```bash
curl http://localhost:8000/api/features
```

Response:
```json
{
  "video_info": true,
  "download": true,
  "status": true,
  ...
}
```

## Permission Levels

### Public Endpoints
No authentication required:
- `GET /` (health check)
- `GET /health`
- `GET /api/features`
- `GET /api/docs`

### Protected Endpoints
Require API key:
- `POST /api/download`
- `GET /api/status/:task_id`
- `DELETE /api/cancel/:task_id`
- All other API endpoints

## SSO Integration

### OpenID Connect Setup

```bash
ENABLE_OIDC=true
OIDC_PROVIDER_URL=https://your-oidc-provider.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

### Login Flow

1. User clicks "Login with SSO"
2. Redirect to OIDC provider
3. User authenticates
4. Redirect back to API with code
5. API exchanges code for token
6. User is authenticated

## API Key Management

### List API Keys

```bash
curl http://localhost:8000/api/auth/keys \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Revoke API Key

```bash
curl -X DELETE http://localhost:8000/api/auth/keys/:key_id \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Security Best Practices

1. **Store secrets securely** - Use environment variables or secret managers
2. **Rotate API keys regularly** - Generate new keys, revoke old ones
3. **Use HTTPS** - Always use HTTPS in production
4. **Limit permissions** - Give users only necessary permissions
5. **Monitor access** - Log and review API access patterns

