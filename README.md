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
- ✅ **GPU Encoding Support**: Use NVENC/Intel QSV/VAAPI hardware acceleration for video encoding
- ✅ **aria2 Integration**: High-speed external downloader support
- ✅ **Deno JavaScript Runtime**: Enhanced JS engine mods with yt-dlp-ejs and Deno

### Technical Stack
- **Backend**: FastAPI (async)
- **Database**: PostgreSQL (task storage)
- **Cache/Queue**: Redis (rate limiting, queue management)
- **Downloader**: yt-dlp with ffmpeg / hardware GPU and aria2/dl
- **Containerization**: Docker + Docker Compose

... (他の内容は以前と同様) ...

---

## 🛠️ Hardware Encoding, aria2, and Deno Runtime

### GPU Encoding Support
Download tasks can use GPU hardware encoders (NVIDIA NVENC, Intel QSV, AMD/Intel VAAPI) for much faster video encoding and lower CPU use. Enable with:
- `ENABLE_GPU_ENCODING=true`
- Set `GPU_ENCODER_TYPE` to `auto`, `nvenc`, `vaapi`, `qsv`, etc.

### aria2 Integration
Large files can be downloaded with aria2 for massive parallel high-speed downloads. Enable with:
- `ENABLE_ARIA2=true`
- Tweak `ARIA2_MAX_CONNECTIONS` and `ARIA2_SPLIT` for fine-tuning.

### Deno + yt-dlp-ejs
Custom JavaScript extraction and enhancement is available via the Deno runtime. Enable with:
- `ENABLE_DENO=true`
- Set `DENO_PATH` if not default (/usr/local/bin/deno)
- yt-dlp-ejs will be used for enhanced JS engine compatibility.

... (他の内容は以前と同様) ...
