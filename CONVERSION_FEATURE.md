# 🎬 Media Conversion Feature

## Overview

This feature adds a powerful, queue-based media conversion system to ytdlp-api. It enables automatic format conversion using ffmpeg with support for both audio and video files, priority-based task scheduling, and comprehensive progress tracking.

## Features

### ✨ Supported Formats

#### Audio Formats
- **MP3** - MPEG Audio Layer III (lossy) - Default bitrate: 192k
- **WAV** - Waveform Audio File Format (lossless)
- **FLAC** - Free Lossless Audio Codec (lossless)
- **AAC** - Advanced Audio Coding (lossy) - Default bitrate: 192k
- **Opus** - Modern codec (lossy) - Default bitrate: 128k
- **Vorbis** - OGG Vorbis (lossy) - Default bitrate: 192k
- **M4A** - MPEG-4 Audio (lossy) - Default bitrate: 192k
- **OGG** - OGG Container (lossy) - Default bitrate: 192k
- **ALAC** - Apple Lossless Audio Codec (lossless)

#### Video Formats
- **MP4** - MPEG-4 Part 14 (H.264 codec)
- **WebM** - WebM Video Format (VP9 codec)
- **MKV** - Matroska Video (H.264 codec)
- **MOV** - QuickTime Movie (ProRes codec)
- **AVI** - Audio Video Interleave
- **FLV** - Flash Video
- **H265/HEVC** - High Efficiency Video Codec (H.265)

### 🚀 Advanced Features

#### 1. **Priority-Based Queue**
- Tasks can be assigned different priority levels
- Higher priority tasks are processed first
- Automatic retry with lower priority on failure

#### 2. **Concurrent Processing**
- Configurable maximum concurrent conversions (default: 2)
- Prevents system overload
- Automatic queue management

#### 3. **GPU Encoding Support**
- NVIDIA NVENC (H.264, HEVC)
- AMD/Intel VAAPI (H.264, HEVC)
- Intel Quick Sync Video (QSV)
- Automatic encoder detection and fallback

#### 4. **Progress Tracking**
- Real-time progress monitoring (0-100%)
- Encoding speed tracking (e.g., 2.5x)
- Detailed conversion statistics

#### 5. **Audio-Specific Features**
- Custom sample rate support (e.g., 44100, 48000 Hz)
- Channel configuration (mono, stereo, 5.1, etc.)
- Custom bitrate control (lossy formats)
- Lossless compression support

#### 6. **Video-Specific Features**
- Hardware acceleration support
- Preset-based quality/speed tradeoff
- Audio extraction mode (audio_only flag)

#### 7. **Error Handling & Retry**
- Automatic retry on transient failures
- Configurable maximum retry attempts
- Detailed error messages
- Failed task history (7 days retention)

#### 8. **Resource Management**
- Automatic cleanup of old tasks
- Configurable retention periods
- Output file cleanup

## API Endpoints

### Create Conversion Task
```
POST /conversion/tasks
```

**Request:**
```json
{
  "source_file_path": "/app/downloads/task123.mp4",
  "source_format": "mp4",
  "target_format": "mp3",
  "target_bitrate": "192k",
  "sample_rate": 44100,
  "channels": 2,
  "audio_only": true,
  "title": "My Song",
  "priority": 1,
  "max_retries": 3
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Conversion task created and queued for mp4 → mp3"
}
```

### Get Conversion Task Details
```
GET /conversion/tasks/{task_id}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "converting",
  "progress": 45.5,
  "source_format": "mp4",
  "target_format": "mp3",
  "source_file_path": "/app/downloads/task123.mp4",
  "output_file_path": "/app/downloads/550e8400-e29b-41d4-a716-446655440000.mp3",
  "output_filename": "550e8400-e29b-41d4-a716-446655440000.mp3",
  "output_file_size": null,
  "error_message": null,
  "created_at": "2025-12-13T05:30:00Z",
  "started_at": "2025-12-13T05:35:00Z",
  "completed_at": null,
  "encoding_speed": 2.5
}
```

### Cancel Conversion Task
```
POST /conversion/tasks/{task_id}/cancel
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "message": "Conversion task ... has been cancelled"
}
```

### Get Queue Statistics
```
GET /conversion/queue/stats
```

**Response:**
```json
{
  "queued": 5,
  "active": 2,
  "completed": 150,
  "failed": 3,
  "cancelled": 2,
  "retried": 1
}
```

### Get Supported Formats
```
GET /conversion/formats
```

### Get Format Details
```
GET /conversion/formats/{format_name}
```

## Configuration

Add these environment variables to your `.env` file:

```bash
# Conversion Settings
MAX_CONCURRENT_CONVERSIONS=2
ENABLE_GPU_ENCODING=true
GPU_ENCODER_TYPE=auto  # auto, nvenc, vaapi, qsv
GPU_ENCODER_PRESET=fast  # fast, medium, slow (NVIDIA)

# Auto-cleanup
AUTO_DELETE_AFTER=604800  # 7 days in seconds
```

## Database Migration

The new `conversion_tasks` table is automatically created when the application starts. Schema includes:

```sql
CREATE TABLE conversion_tasks (
    id VARCHAR(36) PRIMARY KEY,
    source_file_path VARCHAR(512) NOT NULL,
    source_format VARCHAR(10) NOT NULL,
    target_format VARCHAR(10) NOT NULL,
    status ENUM('pending', 'queued', 'converting', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
    progress FLOAT DEFAULT 0.0,
    output_file_path VARCHAR(512),
    output_file_size INT,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    -- ... additional fields
);
```

## Usage Examples

### Example 1: Convert Downloaded MP4 to MP3

```python
import httpx
import asyncio

async def convert_video_to_audio():
    async with httpx.AsyncClient() as client:
        # Create conversion task
        response = await client.post(
            "http://localhost:8000/conversion/tasks",
            json={
                "source_file_path": "/app/downloads/video.mp4",
                "source_format": "mp4",
                "target_format": "mp3",
                "target_bitrate": "192k",
                "sample_rate": 44100,
                "audio_only": True
            }
        )
        task = response.json()
        task_id = task["task_id"]
        
        # Monitor progress
        while True:
            status_response = await client.get(
                f"http://localhost:8000/conversion/tasks/{task_id}"
            )
            status = status_response.json()
            
            print(f"Progress: {status['progress']}% - {status['status']}")
            
            if status["status"] == "completed":
                print(f"Conversion complete! File: {status['output_filename']}")
                break
            elif status["status"] == "failed":
                print(f"Conversion failed: {status['error_message']}")
                break
            
            await asyncio.sleep(1)

asyncio.run(convert_video_to_audio())
```

### Example 2: Batch Convert with Priority

```python
async def batch_convert():
    async with httpx.AsyncClient() as client:
        files = [
            ("video1.mp4", "mp3", 2),  # High priority
            ("video2.mp4", "wav", 1),  # Normal priority
            ("video3.mp4", "flac", 0), # Low priority
        ]
        
        for filename, target_format, priority in files:
            await client.post(
                "http://localhost:8000/conversion/tasks",
                json={
                    "source_file_path": f"/app/downloads/{filename}",
                    "source_format": "mp4",
                    "target_format": target_format,
                    "priority": priority
                }
            )
```

## Performance Considerations

### Hardware Encoding Benefits
- **GPU Encoding**: 2-5x faster than CPU for H.264/HEVC
- **NVIDIA NVENC**: Best performance on NVIDIA GPUs
- **VAAPI**: Good option for AMD/Intel integrated graphics

### Optimization Tips
1. **Set appropriate concurrent limits** based on your hardware
2. **Use GPU encoding** for video conversions when available
3. **Choose suitable presets**: fast for real-time, slow for best quality
4. **Monitor resource usage** via health check endpoints

## Error Handling

### Common Errors

**ffmpeg not found**
- Ensure ffmpeg is installed: `apt install ffmpeg`

**Unsupported format**
- Check `/conversion/formats` endpoint for supported formats

**Conversion timeout**
- Increase timeout or reduce file complexity

**Permission denied**
- Ensure download directory is writable

## Monitoring

### Health Check Endpoints
- `/conversion/queue/stats` - Queue statistics
- `/metrics` - Prometheus metrics (if enabled)

### Log Monitoring
```bash
docker logs -f ytdlp-api | grep conversion
```

## Troubleshooting

### Task stuck in "converting" status
1. Check process with `ps aux | grep ffmpeg`
2. Check error logs for timeout/crash
3. Cancel task and retry

### GPU encoding not working
1. Verify GPU drivers: `nvidia-smi` or `vainfo`
2. Check `GPU_ENCODER_TYPE` setting
3. Check logs for fallback to CPU

### High memory usage
1. Reduce `MAX_CONCURRENT_CONVERSIONS`
2. Check file sizes
3. Monitor with `top` or `docker stats`

## Future Enhancements

- [ ] Batch conversion from parent download
- [ ] Webhook notifications on completion
- [ ] Custom ffmpeg filter chains
- [ ] Subtitle conversion support
- [ ] Streaming output support
- [ ] Advanced codec options (CRF, etc.)

## License

Same as ytdlp-api project
