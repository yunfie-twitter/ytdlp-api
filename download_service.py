import asyncio
import os
import uuid
import json
import re
from typing import Optional, Dict
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
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"Failed to get video info: {stderr.decode()}")
        
        info = json.loads(stdout.decode())
        
        # Extract formats
        formats = []
        if "formats" in info:
            seen = set()
            for f in info["formats"]:
                if f.get("format_id") and f.get("format_note"):
                    key = f"{f.get('height', 'audio')}_{f.get('ext', '')}"
                    if key not in seen:
                        formats.append({
                            "format_id": f["format_id"],
                            "resolution": f.get("format_note", "audio"),
                            "ext": f.get("ext", "unknown"),
                            "filesize": f.get("filesize", 0)
                        })
                        seen.add(key)
        
        return {
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration", 0),
            "view_count": info.get("view_count", 0),
            "like_count": info.get("like_count", 0),
            "uploader": info.get("uploader", "Unknown"),
            "upload_date": info.get("upload_date"),
            "formats": formats[:10]  # Limit to 10 formats
        }
    
    async def create_task(self, url: str, format_type: str, ip_address: str,
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
    
    def _get_format_options(self, format_type: str) -> tuple:
        """Get yt-dlp format string and output extension"""
        format_map = {
            "mp3": ("bestaudio", "mp3"),
            "mp4": ("best[ext=mp4]", "mp4"),
            "best": ("best", "mp4"),
            "audio": ("bestaudio", "m4a"),
            "video": ("bestvideo", "mp4"),
            "webm": ("best[ext=webm]", "webm"),
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
            format_string, ext = self._get_format_options(task.format)
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
            
            # Add post-processing for audio formats
            if task.format.lower() in ["mp3", "wav", "flac", "aac"]:
                cmd.extend(["-x", "--audio-format", task.format.lower()])
                if task.embed_thumbnail:
                    cmd.append("--embed-thumbnail")
            
            if settings.YTDLP_PROXY:
                cmd.extend(["--proxy", settings.YTDLP_PROXY])
            
            if settings.YTDLP_COOKIES_FILE:
                cmd.extend(["--cookies", settings.YTDLP_COOKIES_FILE])
            
            # Start process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
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
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
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