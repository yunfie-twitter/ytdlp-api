"""PROGRESS_TRACKING_GUIDE.md content - moved from root to wiki folder"""
# Progress Tracking Guide

## Overview

Realistic, granular progress updates with support for both WebSocket and polling methods.

## Progress Events

### Download Events
```json
{
  "event": "download.started",
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2025-12-07T12:00:00Z"
}
```

### Progress Events
```json
{
  "event": "download.progress",
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "progress": {
    "downloaded_bytes": 5242880,
    "total_bytes": 104857600,
    "percentage": 5.0,
    "speed_mbps": 2.5,
    "eta_seconds": 42
  },
  "timestamp": "2025-12-07T12:00:05Z"
}
```

### Completion Events
```json
{
  "event": "download.completed",
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "result": {
    "filename": "video.mp4",
    "size_mb": 100,
    "duration_seconds": 3600
  },
  "timestamp": "2025-12-07T12:05:00Z"
}
```

## WebSocket Connection

### Connect
```javascript
const ws = new WebSocket('ws://localhost:8000/api/progress/ws');

ws.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`Download progress: ${progress.progress.percentage}%`);
};
```

### Subscribe to Task
```javascript
ws.send(JSON.stringify({
  "action": "subscribe",
  "task_id": "123e4567-e89b-12d3-a456-426614174000"
}));
```

### Unsubscribe
```javascript
ws.send(JSON.stringify({
  "action": "unsubscribe",
  "task_id": "123e4567-e89b-12d3-a456-426614174000"
}));
```

## Polling Method

### Get Current Progress
```bash
curl http://localhost:8000/api/progress/123e4567-e89b-12d3-a456-426614174000 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Response:
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "state": "downloading",
  "progress": {
    "percentage": 45.5,
    "downloaded_bytes": 47185920,
    "total_bytes": 104857600,
    "speed_mbps": 3.2,
    "eta_seconds": 18
  },
  "timestamp": "2025-12-07T12:02:30Z"
}
```

## Status Codes

| State | Description |
|-------|-------------|
| `pending` | Waiting to start |
| `downloading` | Download in progress |
| `processing` | Post-processing (encoding, etc) |
| `completed` | Download completed successfully |
| `failed` | Download failed |
| `cancelled` | User cancelled the download |

## Error Handling

### Connection Lost
```javascript
ws.onclose = () => {
  console.log('Connection lost, reconnecting...');
  // Implement reconnection logic
};
```

### Error Event
```json
{
  "event": "download.error",
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "error": {
    "type": "network_error",
    "message": "Connection timeout"
  },
  "timestamp": "2025-12-07T12:03:00Z"
}
```

## Performance Optimization

1. **Use WebSocket** for real-time updates when possible
2. **Polling interval** should be 1-5 seconds
3. **Batch updates** when multiple tasks are tracked
4. **Cache progress** locally to reduce requests

