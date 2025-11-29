# yt-dlp Download API

🚀 **Full-featured video/audio download API** powered by FastAPI, Redis, PostgreSQL, and Docker

## ✨ Features

### Core Functionality
- ✅ **Multiple Format Support**: MP3, MP4, WebM, WAV, FLAC, AAC, best quality, audio-only, video-only
- ✅ **Asynchronous Processing**: Non-blocking downloads with `asyncio.create_subprocess_exec`
- ✅ **Progress Tracking**: Real-time progress via WebSocket or polling API
- ✅ **Queue Management**: Concurrent download limits with Redis-backed queue
- ✅ **Rate Limiting**: IP-based rate limiting (configurable via `.env`)
- ✅ **Auto-cleanup**: Automatic deletion of old completed tasks
- ✅ **MP3 Tag Editing**: Embed title and thumbnail in MP3 files
- ✅ **Task Cancellation**: Stop running downloads
- ✅ **Subtitle Download**: Extract subtitles in multiple languages
- ✅ **Video Info API**: Get metadata without downloading

### Technical Stack
- **Backend**: FastAPI (async)
- **Database**: PostgreSQL (task storage)
- **Cache/Queue**: Redis (rate limiting, queue management)
- **Downloader**: yt-dlp with ffmpeg
- **Containerization**: Docker + Docker Compose

---

## 📦 Installation

### Prerequisites
- Docker & Docker Compose
- Git

### Quick Start

```bash
# Clone repository
git clone https://github.com/yunfie-twitter/ytdlp-api.git
cd ytdlp-api

# Copy environment file
cp .env.example .env

# Edit .env if needed
nano .env

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f api
```

API will be available at: **http://localhost:8000**

---

## 🔧 Configuration

Edit `.env` file:

```bash
# Rate Limiting (requests per minute per IP)
RATE_LIMIT_PER_MINUTE=3

# Queue Management (max simultaneous downloads)
MAX_CONCURRENT_DOWNLOADS=3

# Auto-delete completed tasks after (seconds)
AUTO_DELETE_AFTER=3600

# yt-dlp Settings
YTDLP_PROXY=http://proxy:8080  # Optional
YTDLP_COOKIES_FILE=/app/cookies.txt  # Optional
```

---

## 📚 API Endpoints

### 1. Get Video Info

**Without downloading**, get metadata about a video:

```bash
GET /api/info?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

**Response:**
```json
{
  "title": "Rick Astley - Never Gonna Give You Up",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "duration": 213,
  "view_count": 1500000000,
  "like_count": 16000000,
  "uploader": "Rick Astley",
  "formats": [
    {"format_id": "22", "resolution": "720p", "ext": "mp4"},
    {"format_id": "18", "resolution": "360p", "ext": "mp4"}
  ]
}
```

### 2. Create Download Task

```bash
POST /api/download
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format": "mp3",
  "mp3_title": "Never Gonna Give You Up",
  "embed_thumbnail": true
}
```

**Supported Formats:**
- `mp3` - Audio as MP3
- `mp4` - Video as MP4
- `best` - Best quality available
- `audio` - Audio only (m4a)
- `video` - Video only (no audio)
- `webm` - WebM format
- `wav` - Lossless WAV
- `flac` - Lossless FLAC
- `aac` - AAC audio

**Response:**
```json
{
  "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "pending",
  "queue_position": 2,
  "message": "Task created and added to queue"
}
```

### 3. Check Status (Polling)

```bash
GET /api/status/{task_id}
```

**Response:**
```json
{
  "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "downloading",
  "progress": 45.2,
  "filename": "f47ac10b-58cc-4372-a567-0e02b2c3d479.mp3",
  "file_size": 5242880,
  "title": "Never Gonna Give You Up",
  "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "created_at": "2024-11-29T10:00:00Z",
  "completed_at": null
}
```

**Status Values:**
- `pending` - In queue
- `downloading` - Currently downloading
- `completed` - Download finished
- `failed` - Download failed
- `cancelled` - Manually cancelled

### 4. Real-time Progress (WebSocket)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/{task_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress}%`);
  console.log(`Status: ${data.status}`);
};
```

### 5. Download File

```bash
GET /api/download/{task_id}
```

Returns the downloaded file as a stream.

### 6. Cancel Task

```bash
POST /api/cancel/{task_id}
```

**Response:**
```json
{
  "message": "Task cancelled",
  "cancelled": true
}
```

### 7. Delete Task

```bash
DELETE /api/task/{task_id}
```

Deletes task from database and removes file.

### 8. List Tasks

```bash
GET /api/tasks?status=completed&limit=50
```

### 9. Get Thumbnail

```bash
GET /api/thumbnail/{task_id}
```

**Response:**
```json
{
  "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
}
```

### 10. Download Subtitles

```bash
GET /api/subtitles?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&lang=en
```

**Response:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "en",
  "subtitles": "1\n00:00:00,000 --> 00:00:05,000\nWe're no strangers to love..."
}
```

### 11. Queue Statistics

```bash
GET /api/queue/stats
```

**Response:**
```json
{
  "active_downloads": 2,
  "max_concurrent": 3,
  "available_slots": 1
}
```

---

## 💻 Usage Examples

### cURL

```bash
# Get video info
curl "http://localhost:8000/api/info?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Start download
curl -X POST "http://localhost:8000/api/download" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "format": "mp3",
    "mp3_title": "Never Gonna Give You Up",
    "embed_thumbnail": true
  }'

# Check status
curl "http://localhost:8000/api/status/{task_id}"

# Download file
curl -O "http://localhost:8000/api/download/{task_id}"
```

### Python

```python
import requests
import time

# Create download
response = requests.post('http://localhost:8000/api/download', json={
    'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'format': 'mp3',
    'mp3_title': 'Never Gonna Give You Up',
    'embed_thumbnail': True
})

task_id = response.json()['task_id']
print(f'Task created: {task_id}')

# Poll status
while True:
    status = requests.get(f'http://localhost:8000/api/status/{task_id}').json()
    print(f"Progress: {status['progress']}%")
    
    if status['status'] == 'completed':
        print('Download completed!')
        break
    elif status['status'] == 'failed':
        print(f"Error: {status['error_message']}")
        break
    
    time.sleep(2)

# Download file
with open('output.mp3', 'wb') as f:
    file_data = requests.get(f'http://localhost:8000/api/download/{task_id}')
    f.write(file_data.content)
```

### JavaScript (Fetch API)

```javascript
async function downloadVideo(url, format = 'mp4') {
  // Create task
  const response = await fetch('http://localhost:8000/api/download', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({url, format})
  });
  
  const {task_id} = await response.json();
  console.log(`Task ID: ${task_id}`);
  
  // Connect WebSocket for real-time progress
  const ws = new WebSocket(`ws://localhost:8000/ws/${task_id}`);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`${data.status}: ${data.progress}%`);
    
    if (data.status === 'completed') {
      window.location.href = `http://localhost:8000/api/download/${task_id}`;
      ws.close();
    }
  };
}

// Usage
downloadVideo('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'mp3');
```

---

## 🐛 Troubleshooting

### Check Service Status

```bash
docker-compose ps
```

### View Logs

```bash
# All services
docker-compose logs -f

# API only
docker-compose logs -f api

# PostgreSQL
docker-compose logs -f postgres

# Redis
docker-compose logs -f redis
```

### Restart Services

```bash
docker-compose restart
```

### Clean Start

```bash
docker-compose down -v
docker-compose up -d
```

### Access Database

```bash
docker exec -it ytdlp-postgres psql -U ytdlp -d ytdlp_api
```

### Access Redis

```bash
docker exec -it ytdlp-redis redis-cli
```

---

## 🛡️ Security Considerations

1. **Change default passwords** in `.env`
2. **Set SECRET_KEY** to a random value
3. **Configure CORS_ORIGINS** for production
4. **Use reverse proxy** (nginx/Caddy) with HTTPS
5. **Implement authentication** for production use
6. **Rate limiting** protects against abuse

---

## 🚀 Production Deployment

### Using Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 📊 Architecture

```
┌──────────────┐
│    Client    │
└─────┬───────┘
      │
      │ HTTP/WebSocket
      │
┌─────┴─────────────────────┐
│   FastAPI (main.py)      │
│  - Rate Limiter          │
│  - API Endpoints         │
│  - WebSocket Handler     │
└────┬─────────┬────────┘
     │          │
     │          │
┌────┴────┐   ┌─┴─────────────────┐
│  Redis   │   │   PostgreSQL     │
│  Queue   │   │   Task DB        │
└────┬────┘   └────────┬──────┘
     │                  │
     │                  │
┌────┴─────────────────┴──────┐
│   Queue Worker              │
│   - Process Queue           │
│   - Cleanup Old Tasks       │
└──────────┬────────────────┘
           │
           │
┌──────────┴─────────────────┐
│   Download Service         │
│   - yt-dlp execution       │
│   - Progress tracking      │
│   - MP3 tag editing        │
│   - File management        │
└──────────────────────────────┘
```

---

## 📝 License

MIT License - feel free to use in your projects!

---

## 👥 Author

**ゆんふぃ** (yunfie-twitter)
- GitHub: [@yunfie-twitter](https://github.com/yunfie-twitter)
- Website: [notes.yunfie.org](https://notes.yunfie.org/)

---

## ⭐ Contributing

Pull requests are welcome! For major changes, please open an issue first.

---

**Built with ❤️ using FastAPI, yt-dlp, and Docker**