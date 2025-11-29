import asyncio
import os
import uuid
import json
import re
import shutil
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, APIC
from PIL import Image
import httpx

from config import settings
from redis_manager import redis_manager
from database import get_db, DownloadTask

class DownloadService:
    def __init__(self):
        self.download_dir = Path(settings.DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
    
    def _get_gpu_encoder_args(self) -> List[str]:
        """Get GPU encoder arguments based on configuration"""
        if not settings.ENABLE_GPU_ENCODING:
            return []
        
        encoder_type = settings.GPU_ENCODER_TYPE.lower()
        preset = settings.GPU_ENCODER_PRESET
        
        # Auto-detect available encoder
        if encoder_type == "auto":
            if shutil.which("nvidia-smi"):
                encoder_type = "nvenc"
            elif os.path.exists("/dev/dri"):
                encoder_type = "vaapi"
            else:
                return []  # No GPU encoder available
        
        postprocessor_args = []
        
        if encoder_type == "nvenc":
            # NVIDIA NVENC encoder
            postprocessor_args = [
                "-c:v", "h264_nvenc",
                "-preset", preset,
                "-b:v", "5M"
            ]
        elif encoder_type == "vaapi":
            # AMD/Intel VAAPI encoder
            postprocessor_args = [
                "-vaapi_device", "/dev/dri/renderD128",
                "-vf", "format=nv12,hwupload",
                "-c:v", "h264_vaapi",
                "-b:v", "5M"
            ]
        elif encoder_type == "qsv":
            # Intel Quick Sync Video
            postprocessor_args = [
                "-c:v", "h264_qsv",
                "-preset", preset,
                "-b:v", "5M"
            ]
        
        return postprocessor_args
    
    def _get_aria2_args(self) -> List[str]:
        """Get aria2 external downloader arguments"""
        if not settings.ENABLE_ARIA2:
            return []
        
        return [
            "--external-downloader", "aria2c",
            "--external-downloader-args",
            f"aria2c:-x {settings.ARIA2_MAX_CONNECTIONS} -s {settings.ARIA2_SPLIT} -k 1M"
        ]
    
    def _get_deno_env(self) -> Dict[str, str]:
        """Get environment variables for Deno JavaScript runtime"""
        env = os.environ.copy()
        
        if settings.ENABLE_DENO and os.path.exists(settings.DENO_PATH):
            # Set DENO_DIR environment variable for yt-dlp-ejs
            env["DENO_DIR"] = str(Path(settings.DENO_PATH).parent)
            # Add Deno to PATH
            env["PATH"] = f"{Path(settings.DENO_PATH).parent}:{env.get('PATH', '')}"
        
        return env
    
    async def get_video_info(self, url: str) -> dict:
        """Get video information without downloading"""
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
            url
        ]
        
        if settings.YTDLP_PROXY:
            cmd.extend(["--proxy", settings.YTDLP_PROXY])
        
        # Get environment with Deno support
        env = self._get_deno_env()
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"Failed to get video info: {stderr.decode()}")
        
        info = json.loads(stdout.decode())
        
        # Extract formats with detailed information
        formats = []
        available_qualities = set()
        available_audio_formats = set()
        
        if "formats" in info:
            seen = set()
            for f in info["formats"]:
                format_id = f.get("format_id")
                if not format_id:
                    continue
                
                # 画質情報を収集
                height = f.get("height")
                if height:
                    available_qualities.add(f"{height}p")
                
                # 音声フォーマットを収集
                acodec = f.get("acodec")
                if acodec and acodec != "none":
                    available_audio_formats.add(f.get("ext", "unknown"))
                
                # Format詳細を追加
                key = f"{format_id}_{f.get('ext', '')}"
                if key not in seen:
                    formats.append({
                        "format_id": format_id,
                        "resolution": f.get("format_note", f"{height}p" if height else "audio"),
                        "ext": f.get("ext", "unknown"),
                        "filesize": f.get("filesize"),
                        "fps": f.get("fps"),
                        "vcodec": f.get("vcodec"),
                        "acodec": acodec
                    })
                    seen.add(key)
        
        # 画質一覧をソート
        quality_order = ["2160p", "1440p", "1080p", "720p", "480p", "360p", "240p", "144p"]
        sorted_qualities = [q for q in quality_order if q in available_qualities]
        
        return {
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration", 0),
            "view_count": info.get("view_count", 0),
            "like_count": info.get("like_count", 0),
            "uploader": info.get("uploader", "Unknown"),
            "upload_date": info.get("upload_date"),
            "formats": formats[:30],  # Limit to 30 formats
            "available_qualities": sorted_qualities,
            "available_audio_formats": sorted(list(available_audio_formats))
        }
    
    async def create_task(self, url: str, format_type: str, ip_address: str,
                         format_id: Optional[str] = None,
                         quality: Optional[str] = None,
                         mp3_title: Optional[str] = None,
                         embed_thumbnail: bool = False) -> str:
        """Create a new download task"""
        task_id = str(uuid.uuid4())
        
        # Get video info
        try:
            info = await self.get_video_info(url)
        except Exception as e:
            info = {"title": None, "thumbnail": None, "duration": None}
        
        # Create database entry
        db = next(get_db())
        task = DownloadTask(
            id=task_id,
            url=url,
            format=format_type,
            format_id=format_id,
            quality=quality,
            status="pending",
            ip_address=ip_address,
            title=info.get("title"),
            thumbnail_url=info.get("thumbnail"),
            duration=info.get("duration"),
            mp3_title=mp3_title,
            embed_thumbnail=embed_thumbnail
        )
        db.add(task)
        db.commit()
        db.close()
        
        # Add to queue
        await redis_manager.add_to_queue(task_id)
        
        return task_id
    
    def _get_format_options(self, format_type: str, format_id: Optional[str] = None, 
                           quality: Optional[str] = None) -> tuple:
        """Get yt-dlp format string and output extension"""
        # 特定のformat_idが指定されている場合はそれを優先
        if format_id:
            # 拡張子を推定
            ext = "mp4" if "+" in format_id else format_type.lower()
            return (format_id, ext)
        
        # quality指定がある場合
        if quality:
            if quality == "best":
                return ("bestvideo+bestaudio/best", "mp4")
            elif quality == "worst":
                return ("worstvideo+worstaudio/worst", "mp4")
            elif quality.endswith("p"):
                # 解像度指定 (例: "1080p")
                height = quality[:-1]
                format_str = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
                return (format_str, "mp4")
        
        # デフォルトのフォーマットマッピング
        format_map = {
            "mp3": ("bestaudio", "mp3"),
            "mp4": ("bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", "mp4"),
            "best": ("bestvideo+bestaudio/best", "mp4"),
            "audio": ("bestaudio", "m4a"),
            "video": ("bestvideo", "mp4"),
            "webm": ("bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]", "webm"),
            "wav": ("bestaudio", "wav"),
            "flac": ("bestaudio", "flac"),
            "aac": ("bestaudio", "aac")
        }
        return format_map.get(format_type.lower(), ("best", "mp4"))
    
    async def download(self, task_id: str):
        """Execute download task"""
        db = next(get_db())
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        
        if not task:
            db.close()
            return
        
        try:
            # Update status
            task.status = "downloading"
            db.commit()
            
            # Prepare output path
            format_string, ext = self._get_format_options(
                task.format, 
                task.format_id, 
                task.quality
            )
            output_template = str(self.download_dir / f"{task_id}.%(ext)s")
            
            # Build command
            cmd = [
                "yt-dlp",
                "-f", format_string,
                "--no-playlist",
                "--newline",
                "-o", output_template,
                task.url
            ]
            
            # Add aria2 external downloader
            aria2_args = self._get_aria2_args()
            if aria2_args:
                cmd.extend(aria2_args)
            
            # Add post-processing for audio formats
            if task.format.lower() in ["mp3", "wav", "flac", "aac"]:
                cmd.extend(["-x", "--audio-format", task.format.lower()])
                if task.embed_thumbnail:
                    cmd.append("--embed-thumbnail")
            
            # Add GPU encoding for video formats
            if task.format.lower() in ["mp4", "webm", "best", "video"]:
                gpu_args = self._get_gpu_encoder_args()
                if gpu_args:
                    cmd.extend(["--postprocessor-args", " ".join(gpu_args)])
            
            if settings.YTDLP_PROXY:
                cmd.extend(["--proxy", settings.YTDLP_PROXY])
            
            if settings.YTDLP_COOKIES_FILE:
                cmd.extend(["--cookies", settings.YTDLP_COOKIES_FILE])
            
            # Get environment with Deno support
            env = self._get_deno_env()
            
            # Start process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            self.active_processes[task_id] = process
            task.process_id = process.pid
            db.commit()
            
            # Monitor progress
            async for line in process.stdout:
                line_str = line.decode().strip()
                
                # Parse progress
                progress_match = re.search(r'(\d+\.\d+)%', line_str)
                if progress_match:
                    progress = float(progress_match.group(1))
                    task.progress = progress
                    db.commit()
                    
                    # Update Redis
                    await redis_manager.set_progress(task_id, {
                        "progress": progress,
                        "status": "downloading"
                    })
            
            await process.wait()
            
            if process.returncode == 0:
                # Find downloaded file
                files = list(self.download_dir.glob(f"{task_id}.*"))
                if files:
                    file_path = files[0]
                    task.file_path = str(file_path)
                    task.filename = file_path.name
                    task.file_size = file_path.stat().st_size
                    
                    # Apply MP3 tags if needed
                    if task.format.lower() == "mp3" and task.mp3_title:
                        await self._apply_mp3_tags(file_path, task)
                    
                    task.status = "completed"
                    task.progress = 100.0
                    task.completed_at = datetime.utcnow()
                else:
                    task.status = "failed"
                    task.error_message = "File not found after download"
            else:
                stderr = await process.stderr.read()
                task.status = "failed"
                task.error_message = stderr.decode()[:500]
            
            db.commit()
            
        except asyncio.CancelledError:
            task.status = "cancelled"
            db.commit()
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)[:500]
            db.commit()
        finally:
            db.close()
            if task_id in self.active_processes:
                del self.active_processes[task_id]
            await redis_manager.remove_from_active(task_id)
    
    async def _apply_mp3_tags(self, file_path: Path, task: DownloadTask):
        """Apply MP3 ID3 tags"""
        try:
            audio = MP3(str(file_path), ID3=ID3)
            
            # Add title
            if task.mp3_title:
                audio["TIT2"] = TIT2(encoding=3, text=task.mp3_title)
            
            # Add thumbnail
            if task.embed_thumbnail and task.thumbnail_url:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(task.thumbnail_url)
                    if resp.status_code == 200:
                        # Save temp thumbnail
                        thumb_path = file_path.parent / f"{task.id}_thumb.jpg"
                        thumb_path.write_bytes(resp.content)
                        
                        # Convert and resize
                        img = Image.open(thumb_path)
                        img.thumbnail((500, 500))
                        img.save(thumb_path, "JPEG")
                        
                        # Embed
                        with open(thumb_path, "rb") as f:
                            audio["APIC"] = APIC(
                                encoding=3,
                                mime="image/jpeg",
                                type=3,
                                desc="Cover",
                                data=f.read()
                            )
                        
                        thumb_path.unlink()
            
            audio.save()
        except Exception as e:
            print(f"Failed to apply MP3 tags: {e}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running download"""
        if task_id in self.active_processes:
            process = self.active_processes[task_id]
            process.terminate()
            await asyncio.sleep(1)
            if process.returncode is None:
                process.kill()
            return True
        return False
    
    async def get_subtitles(self, url: str, lang: str = "en") -> Optional[str]:
        """Download subtitles"""
        cmd = [
            "yt-dlp",
            "--write-subs",
            "--sub-lang", lang,
            "--skip-download",
            "--sub-format", "srt",
            "-o", str(self.download_dir / "temp_sub.%(ext)s"),
            url
        ]
        
        # Get environment with Deno support
        env = self._get_deno_env()
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        await process.wait()
        
        # Find subtitle file
        sub_files = list(self.download_dir.glob("temp_sub.*.srt"))
        if sub_files:
            content = sub_files[0].read_text(encoding="utf-8")
            sub_files[0].unlink()
            return content
        return None

download_service = DownloadService()