# Progress Tracking API Guide - ytdlp-api v1.0.6

## Overview

The Progress Tracking API provides real-time monitoring of download tasks with detailed progress information, bandwidth statistics, and event history.

---

## Features

✅ **Real-time Progress**: Get live progress updates (0-100%)
✅ **Speed Monitoring**: Track download speed in bytes per second
✅ **ETA Calculation**: Automatic time-to-completion estimation
✅ **Event History**: Complete audit trail of task events
✅ **Bandwidth Stats**: Aggregate bandwidth usage across tasks
✅ **Batch Monitoring**: Track multiple tasks simultaneously
✅ **Status Summary**: Overall progress summaries

---

## Endpoints

### 1. Get Task Progress (Detailed)

```
GET /api/progress/tasks/{task_id}
```

**Returns**: Complete progress information including speeds and ETAs

**Example Request**:
```bash
curl -X GET http://localhost:8000/api/progress/tasks/abc123-uuid \
  -H "Authorization: Bearer <token>"
```

**Example Response**:
```json
{
  "task_id": "abc123-uuid",
  "url": "https://example.com/video.mp4",
  "title": "Sample Video",
  "status": "downloading",
  "progress": 45.5,
  "current_bytes": 452000000,
  "total_bytes": 995000000,
  "speed_bps": 2500000.0,
  "eta_seconds": 217.2,
  "filename": "video.mp4",
  "file_size": null,
  "error_message": null,
  "created_at": "2025-12-07T10:00:00",
  "started_at": "2025-12-07T10:00:15",
  "completed_at": null
}
```

**Response Fields**:
- `task_id`: Unique task identifier
- `status`: Current status (pending, downloading, processing, completed, failed, cancelled)
- `progress`: Download progress (0-100%)
- `current_bytes`: Bytes downloaded so far
- `total_bytes`: Total file size in bytes
- `speed_bps`: Current download speed in bytes per second
- `eta_seconds`: Estimated time to completion in seconds
- `filename`: Output filename
- `file_size`: Final file size after completion
- `error_message`: Error details if failed
- Timestamps: Creation, start, and completion times

---

### 2. Get Task Summary

```
GET /api/progress/tasks/{task_id}/summary
```

**Returns**: Simplified progress summary

**Example Request**:
```bash
curl -X GET http://localhost:8000/api/progress/tasks/abc123-uuid/summary
```

**Example Response**:
```json
{
  "task_id": "abc123-uuid",
  "status": "downloading",
  "progress": 45.5,
  "speed_bps": 2500000.0,
  "eta_seconds": 217.2,
  "time_remaining": "3m 37s"
}
```

**Response Fields**:
- `progress`: Current progress percentage
- `speed_bps`: Download speed in bytes/second
- `eta_seconds`: Estimated seconds remaining
- `time_remaining`: Human-readable time (e.g., "3m 37s")

---

### 3. Get Task Events

```
GET /api/progress/tasks/{task_id}/events?limit=100
```

**Returns**: Complete event history for the task

**Query Parameters**:
- `limit` (optional): Number of events to return (1-500, default: 100)

**Example Request**:
```bash
curl -X GET "http://localhost:8000/api/progress/tasks/abc123-uuid/events?limit=50"
```

**Example Response**:
```json
[
  {
    "event": "task_created",
    "timestamp": "2025-12-07T10:00:00",
    "details": {
      "title": "Sample Video",
      "url": "https://example.com/video"
    }
  },
  {
    "event": "download_started",
    "timestamp": "2025-12-07T10:00:15",
    "details": {
      "process_id": 12345
    }
  },
  {
    "event": "progress_update",
    "timestamp": "2025-12-07T10:05:30",
    "details": {
      "progress": 45.5,
      "speed_bps": 2500000.0,
      "current_bytes": 452000000,
      "total_bytes": 995000000
    }
  },
  {
    "event": "task_completed",
    "timestamp": "2025-12-07T10:10:00",
    "details": {
      "file_path": "/downloads/abc123.mp4",
      "file_size": 995000000
    }
  }
]
```

**Event Types**:
- `task_created`: Task initialized
- `download_started`: Download process started
- `progress_update`: Download progress updated
- `post_processing`: Started post-processing (encoding, tagging, etc.)
- `task_completed`: Download completed successfully
- `task_failed`: Download failed
- `task_cancelled`: Download was cancelled

---

### 4. Get All Tasks Progress

```
GET /api/progress/tasks?status=downloading&limit=50
```

**Returns**: Progress for multiple tasks

**Query Parameters**:
- `status` (optional): Filter by status (pending, downloading, completed, failed, cancelled)
- `limit` (optional): Max tasks to return (1-500, default: 50)

**Example Request**:
```bash
curl -X GET "http://localhost:8000/api/progress/tasks?status=downloading&limit=25"
```

**Example Response**:
```json
{
  "total_tasks": 25,
  "completed": 5,
  "downloading": 18,
  "failed": 2,
  "cancelled": 0,
  "pending": 0,
  "overall_progress": 42.5,
  "tasks": [
    {
      "task_id": "task-1",
      "title": "Video 1",
      "status": "downloading",
      "progress": 45.5,
      "speed_bps": 2500000.0
    },
    {
      "task_id": "task-2",
      "title": "Video 2",
      "status": "downloading",
      "progress": 32.2,
      "speed_bps": 1800000.0
    }
  ]
}
```

**Response Fields**:
- `total_tasks`: Number of tasks
- `completed/downloading/failed/cancelled/pending`: Count by status
- `overall_progress`: Average progress across all tasks
- `tasks`: Array of task progress summaries

---

### 5. Get Progress Statistics

```
GET /api/progress/stats
```

**Returns**: Aggregate statistics about all tasks

**Example Request**:
```bash
curl -X GET http://localhost:8000/api/progress/stats
```

**Example Response**:
```json
{
  "total_tasks": 45,
  "overall_progress": 52.3,
  "by_status": {
    "completed": {
      "count": 10,
      "avg_progress": 100.0,
      "max_progress": 100.0
    },
    "downloading": {
      "count": 20,
      "avg_progress": 45.2,
      "max_progress": 98.5
    },
    "pending": {
      "count": 12,
      "avg_progress": 0.0,
      "max_progress": 0.0
    },
    "failed": {
      "count": 3,
      "avg_progress": 15.0,
      "max_progress": 45.0
    }
  }
}
```

**Statistics Provided**:
- `total_tasks`: Total number of tasks
- `overall_progress`: Average progress across all tasks
- `by_status`: Breakdown by status with counts and progress metrics

---

### 6. Get Bandwidth Statistics

```
GET /api/progress/bandwidth?minutes=5
```

**Returns**: Real-time bandwidth usage

**Query Parameters**:
- `minutes` (optional): Time window to analyze (1-60, default: 5)

**Example Request**:
```bash
curl -X GET "http://localhost:8000/api/progress/bandwidth?minutes=5"
```

**Example Response**:
```json
{
  "downloading_count": 18,
  "total_speed_bps": 45000000.0,
  "total_speed_formatted": "45.00 MB/s",
  "average_speed_bps": 2500000.0,
  "average_speed_formatted": "2.50 MB/s"
}
```

**Response Fields**:
- `downloading_count`: Number of active downloads
- `total_speed_bps`: Combined bandwidth of all downloads
- `total_speed_formatted`: Human-readable total speed
- `average_speed_bps`: Average speed per download
- `average_speed_formatted`: Human-readable average speed

---

## Speed Units

Speeds are reported in both raw and human-readable formats:

| Unit | Conversion |
|------|------------|
| B/s | Bytes per second |
| KB/s | Kilobytes per second (÷ 1024) |
| MB/s | Megabytes per second (÷ 1024²) |
| GB/s | Gigabytes per second (÷ 1024³) |

**Examples**:
- 2,500,000 B/s = 2.50 MB/s
- 45,000,000 B/s = 45.00 MB/s
- 1,000,000,000 B/s = 1000.00 MB/s = 0.98 GB/s

---

## Status Codes

### Successful Responses

- **200 OK**: Request successful

### Client Errors

- **400 Bad Request**: Invalid parameters
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Feature disabled or permission denied
- **404 Not Found**: Task not found

### Server Errors

- **500 Internal Server Error**: Unexpected server error
- **503 Service Unavailable**: Service unavailable

---

## Usage Examples

### Example 1: Monitor Single Download

```python
import httpx
import time

task_id = "abc123-uuid"
token = "your-api-key"

headers = {"Authorization": f"Bearer {token}"}

while True:
    response = httpx.get(
        f"http://localhost:8000/api/progress/tasks/{task_id}/summary",
        headers=headers
    )
    
    data = response.json()
    print(f"Progress: {data['progress']:.1f}%")
    print(f"Speed: {data['speed_bps'] / (1024**2):.2f} MB/s")
    print(f"Time remaining: {data['time_remaining']}")
    
    if data['status'] in ['completed', 'failed', 'cancelled']:
        break
    
    time.sleep(5)  # Update every 5 seconds
```

### Example 2: Batch Monitor Multiple Downloads

```python
import httpx

token = "your-api-key"
headers = {"Authorization": f"Bearer {token}"}

response = httpx.get(
    "http://localhost:8000/api/progress/tasks?status=downloading",
    headers=headers
)

data = response.json()
print(f"Total tasks: {data['total_tasks']}")
print(f"Overall progress: {data['overall_progress']:.1f}%")

for task in data['tasks']:
    print(f"  {task['title']}: {task['progress']:.1f}%")
```

### Example 3: Get Event History

```python
import httpx

task_id = "abc123-uuid"
token = "your-api-key"

headers = {"Authorization": f"Bearer {token}"}

response = httpx.get(
    f"http://localhost:8000/api/progress/tasks/{task_id}/events",
    headers=headers
)

for event in response.json():
    print(f"{event['timestamp']} - {event['event']}")
    if event['event'] == 'progress_update':
        progress = event['details']['progress']
        speed = event['details']['speed_bps'] / (1024**2)
        print(f"  Progress: {progress}%, Speed: {speed:.2f} MB/s")
```

### Example 4: Monitor Bandwidth Usage

```python
import httpx
import time

token = "your-api-key"
headers = {"Authorization": f"Bearer {token}"}

while True:
    response = httpx.get(
        "http://localhost:8000/api/progress/bandwidth",
        headers=headers
    )
    
    data = response.json()
    print(f"Active downloads: {data['downloading_count']}")
    print(f"Total bandwidth: {data['total_speed_formatted']}")
    print(f"Average per download: {data['average_speed_formatted']}")
    print()
    
    time.sleep(10)  # Update every 10 seconds
```

---

## Configuration

### Enable/Disable Progress Tracking

```bash
# .env
ENABLE_FEATURE_PROGRESS_TRACKING=true
```

Disabled progress endpoints return **403 Forbidden**.

---

## Performance Considerations

### Update Frequency

- Progress updates recorded: Every 1-5% or every ~5 seconds
- Events stored: Last 100 events per task
- Redis TTL: 7 days

### Polling Recommendations

- **User Interfaces**: Poll every 1-5 seconds for smooth updates
- **Dashboards**: Poll every 10-30 seconds for aggregate stats
- **Monitoring Systems**: Poll every 5-10 minutes for health checks

### Bandwidth Impact

- Single task progress: ~500 bytes per request
- All tasks progress: ~1-5 KB per request
- Event history: ~10-50 KB per task

---

## WebSocket Real-Time Updates (Coming Soon)

For true real-time progress updates, WebSocket support is planned:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/progress/stream/task-id');

ws.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`Progress: ${progress.progress}%`);
};
```

---

## Troubleshooting

### Issue: "Task not found"

**Solution**: Verify the task_id is correct and the task hasn't been deleted

### Issue: Progress not updating

**Solution**: 
1. Check if download is actually in progress: `GET /api/progress/tasks/{id}/summary`
2. Verify Redis connection: `GET /health`
3. Check logs for errors

### Issue: ETA always null

**Solution**: ETA requires both file size and download speed. Check:
- `total_bytes` > 0
- `speed_bps` > 0

### Issue: Feature disabled error

**Solution**: Enable progress tracking in `.env`:
```bash
ENABLE_FEATURE_PROGRESS_TRACKING=true
```

---

**Last Updated**: 2025-12-07  
**Version**: 1.0.6  
**Status**: Production Ready ✅
