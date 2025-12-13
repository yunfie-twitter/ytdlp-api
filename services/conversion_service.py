"""Service for handling media file conversions using ffmpeg"""
import asyncio
import os
import uuid
import logging
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
import re

from core.config import settings
from core.validation.conversion_validation import conversion_validator
from infrastructure.redis_manager import redis_manager
from infrastructure.database import get_db, ConversionTask
from infrastructure.conversion_models import ConversionStatus

logger = logging.getLogger(__name__)


class ConversionService:
    """Service for converting media files using ffmpeg"""
    
    def __init__(self):
        self.download_dir = Path(settings.DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.PROCESS_TIMEOUT = 14400  # 4 hours for large file conversions
        logger.info(f"ConversionService initialized with directory: {self.download_dir}")
    
    def _check_ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available in PATH"""
        result = os.system("ffmpeg -version > /dev/null 2>&1")
        return result == 0
    
    def _parse_ffmpeg_duration(self, output: str) -> Optional[float]:
        """Parse duration from ffmpeg output (HH:MM:SS.mm format)"""
        match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})', output)
        if match:
            hours, minutes, seconds = map(float, match.groups())
            return hours * 3600 + minutes * 60 + seconds
        return None
    
    def _parse_ffmpeg_progress(self, line: str, total_duration: float) -> Optional[float]:
        """Parse progress from ffmpeg output"""
        # Looking for: time=00:05:32.50
        match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
        if match:
            hours, minutes, seconds = map(float, match.groups())
            current_time = hours * 3600 + minutes * 60 + seconds
            if total_duration > 0:
                progress = min(100.0, (current_time / total_duration) * 100)
                return progress
        return None
    
    def _parse_encoding_speed(self, line: str) -> Optional[float]:
        """Parse encoding speed from ffmpeg output (e.g., 2.5x)"""
        # Looking for: speed=2.5x
        match = re.search(r'speed=([\d.]+)x', line)
        if match:
            return float(match.group(1))
        return None
    
    def _build_ffmpeg_command(
        self,
        input_file: Path,
        output_file: Path,
        target_format: str,
        target_bitrate: Optional[str] = None,
        target_codec: Optional[str] = None,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        audio_only: bool = False,
        gpu_enabled: bool = False
    ) -> List[str]:
        """Build ffmpeg command for conversion"""
        cmd = ["ffmpeg", "-i", str(input_file)]
        
        target_fmt = target_format.lower()
        
        # Video conversion settings
        if not audio_only and conversion_validator.is_video_format(target_fmt):
            # Video codec selection
            if gpu_enabled and settings.ENABLE_GPU_ENCODING:
                encoder_args = self._get_gpu_encoder_args(target_fmt)
                cmd.extend(encoder_args)
            else:
                # CPU encoding
                codec = target_codec or self._get_default_video_codec(target_fmt)
                if codec:
                    cmd.extend(["-c:v", codec])
            
            # Preset (quality/speed tradeoff)
            if gpu_enabled:
                cmd.extend(["-preset", settings.GPU_ENCODER_PRESET])
            else:
                cmd.extend(["-preset", "medium"])  # Default CPU preset
            
            # Bitrate for video
            if target_bitrate:
                cmd.extend(["-b:v", target_bitrate])
            else:
                cmd.extend(["-b:v", "5M"])  # Default 5Mbps for video
            
            # Video filters
            cmd.extend(["-c:a", "aac"])  # Always use AAC for audio in video
        
        # Audio conversion settings
        if audio_only or conversion_validator.is_audio_format(target_fmt):
            # Audio codec
            codec = target_codec or self._get_default_audio_codec(target_fmt)
            if codec:
                cmd.extend(["-c:a", codec])
            
            # Audio bitrate (skip for lossless)
            fmt_info = conversion_validator.get_format_info(target_fmt)
            if not fmt_info.get("lossless"):
                bitrate = target_bitrate or fmt_info.get("default_bitrate")
                if bitrate:
                    cmd.extend(["-b:a", bitrate])
            
            # Sample rate
            if sample_rate:
                cmd.extend(["-ar", str(sample_rate)])
            
            # Channels
            if channels:
                cmd.extend(["-ac", str(channels)])
            elif audio_only:
                # Default to stereo for audio-only conversions
                cmd.extend(["-ac", "2"])
        
        # Output file settings
        # Format container if needed
        if target_fmt == "m4a":
            cmd.extend(["-f", "ipod"])  # m4a uses ipod container
        elif target_fmt == "ogg":
            cmd.extend(["-f", "ogg"])
        
        # Progress output and other options
        cmd.extend([
            "-progress", "pipe:1",  # Progress output to stdout
            "-y",  # Overwrite output file
            str(output_file)
        ])
        
        return cmd
    
    def _get_gpu_encoder_args(self, format_str: str) -> List[str]:
        """Get GPU encoder arguments based on configuration"""
        if not settings.ENABLE_GPU_ENCODING:
            return []
        
        encoder_type = settings.GPU_ENCODER_TYPE.lower()
        preset = settings.GPU_ENCODER_PRESET
        
        # Auto-detect available encoder
        if encoder_type == "auto":
            if os.system("nvidia-smi > /dev/null 2>&1") == 0:
                encoder_type = "nvenc"
                logger.info("GPU encoding: NVIDIA NVENC detected")
            elif os.path.exists("/dev/dri"):
                encoder_type = "vaapi"
                logger.info("GPU encoding: VAAPI detected")
            else:
                logger.info("GPU encoding: No compatible GPU encoder found")
                return []
        
        args = []
        
        if format_str == "mp4":
            if encoder_type == "nvenc":
                args = ["-c:v", "h264_nvenc", "-preset", preset]
            elif encoder_type == "vaapi":
                args = [
                    "-vaapi_device", "/dev/dri/renderD128",
                    "-vf", "format=nv12,hwupload",
                    "-c:v", "h264_vaapi"
                ]
            elif encoder_type == "qsv":
                args = ["-c:v", "h264_qsv", "-preset", preset]
        elif format_str == "h265":
            if encoder_type == "nvenc":
                args = ["-c:v", "hevc_nvenc", "-preset", preset]
            elif encoder_type == "vaapi":
                args = [
                    "-vaapi_device", "/dev/dri/renderD128",
                    "-vf", "format=nv12,hwupload",
                    "-c:v", "hevc_vaapi"
                ]
            elif encoder_type == "qsv":
                args = ["-c:v", "hevc_qsv", "-preset", preset]
        
        return args
    
    def _get_default_video_codec(self, format_str: str) -> Optional[str]:
        """Get default video codec for format"""
        codec_map = {
            "mp4": "libx264",
            "webm": "libvpx-vp9",
            "mkv": "libx264",
            "mov": "prores",
            "avi": "mpeg4",
            "h265": "libx265",
            "flv": "mpeg4"
        }
        return codec_map.get(format_str.lower())
    
    def _get_default_audio_codec(self, format_str: str) -> Optional[str]:
        """Get default audio codec for format"""
        fmt_info = conversion_validator.get_format_info(format_str)
        return fmt_info.get("codec")
    
    async def create_task(
        self,
        source_file_path: str,
        source_format: str,
        target_format: str,
        ip_address: str,
        target_bitrate: Optional[str] = None,
        target_codec: Optional[str] = None,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        audio_only: bool = False,
        title: Optional[str] = None,
        priority: int = 0,
        max_retries: int = 3
    ) -> str:
        """Create a new conversion task"""
        task_id = str(uuid.uuid4())
        
        # Validate parameters
        is_valid, error_msg = conversion_validator.validate_conversion_params(
            source_format, target_format, target_bitrate, sample_rate, channels
        )
        
        if not is_valid:
            logger.error(f"Conversion validation failed: {error_msg}")
            raise ValueError(error_msg)
        
        # Suggest bitrate if not provided and needed
        if not target_bitrate and conversion_validator.is_audio_format(target_format):
            target_bitrate = conversion_validator.suggest_bitrate(None, target_format)
        
        db = next(get_db())
        try:
            task = ConversionTask(
                id=task_id,
                source_file_path=source_file_path,
                source_format=source_format,
                target_format=target_format,
                target_bitrate=target_bitrate,
                target_codec=target_codec,
                sample_rate=sample_rate,
                channels=channels,
                audio_only=audio_only,
                status=ConversionStatus.PENDING,
                ip_address=ip_address,
                title=title or Path(source_file_path).stem,
                priority=priority,
                max_retries=max_retries
            )
            db.add(task)
            db.commit()
            logger.info(f"Conversion task created: {task_id} ({source_format}->{target_format})")
        finally:
            db.close()
        
        return task_id
    
    async def convert(
        self,
        task_id: str,
        gpu_enabled: bool = False
    ):
        """Execute conversion task"""
        db = next(get_db())
        task = db.query(ConversionTask).filter(ConversionTask.id == task_id).first()
        
        if not task:
            logger.error(f"Conversion: Task not found: {task_id}")
            db.close()
            return
        
        process = None
        try:
            # Check ffmpeg availability
            if not self._check_ffmpeg_available():
                raise RuntimeError("ffmpeg is not available in PATH")
            
            # Verify source file exists
            source_path = Path(task.source_file_path)
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {task.source_file_path}")
            
            # Get source file info
            source_size = source_path.stat().st_size
            
            task.status = ConversionStatus.CONVERTING
            task.started_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Starting conversion for task: {task_id}")
            
            # Prepare output file
            output_filename = f"{task_id}.{task.target_format.lower()}"
            output_path = self.download_dir / output_filename
            
            # Build conversion command
            cmd = self._build_ffmpeg_command(
                input_file=source_path,
                output_file=output_path,
                target_format=task.target_format,
                target_bitrate=task.target_bitrate,
                target_codec=task.target_codec,
                sample_rate=task.sample_rate,
                channels=task.channels,
                audio_only=task.audio_only,
                gpu_enabled=gpu_enabled
            )
            
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            
            # Start ffmpeg process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.active_processes[task_id] = process
            task.process_id = process.pid
            db.commit()
            logger.info(f"Conversion process started for task {task_id} (PID: {process.pid})")
            
            total_duration = None
            
            try:
                # Monitor progress
                async for line in process.stdout:
                    line_str = line.decode().strip()
                    
                    # Parse duration from first pass
                    if not total_duration:
                        total_duration = self._parse_ffmpeg_duration(line_str)
                    
                    # Update progress
                    if total_duration and total_duration > 0:
                        progress = self._parse_ffmpeg_progress(line_str, total_duration)
                        if progress is not None:
                            task.progress = progress
                            
                            # Update encoding speed
                            speed = self._parse_encoding_speed(line_str)
                            if speed is not None:
                                task.encoding_speed = speed
                            
                            db.commit()
                            
                            await redis_manager.set_progress(task_id, {
                                "progress": progress,
                                "status": "converting",
                                "speed": task.encoding_speed
                            })
                
                await asyncio.wait_for(process.wait(), timeout=self.PROCESS_TIMEOUT)
            except asyncio.TimeoutError:
                logger.error(f"Conversion timeout for task {task_id}")
                process.kill()
                task.status = ConversionStatus.FAILED
                task.error_message = "Conversion timed out (exceeded 4 hours)"
                db.commit()
                return
            
            # Check result
            if process.returncode == 0:
                if output_path.exists():
                    output_size = output_path.stat().st_size
                    task.output_file_path = str(output_path)
                    task.output_filename = output_filename
                    task.output_file_size = output_size
                    task.status = ConversionStatus.COMPLETED
                    task.progress = 100.0
                    task.completed_at = datetime.utcnow()
                    
                    compression_ratio = (1 - output_size / source_size) * 100 if source_size > 0 else 0
                    
                    logger.info(
                        f"Conversion completed for task {task_id}: "
                        f"{source_size} bytes -> {output_size} bytes "
                        f"(compression: {compression_ratio:.1f}%)"
                    )
                else:
                    task.status = ConversionStatus.FAILED
                    task.error_message = "Output file not found after conversion"
                    logger.error(f"Output file not found after conversion for task {task_id}")
            else:
                stderr = await process.stderr.read()
                task.status = ConversionStatus.FAILED
                error_output = stderr.decode()
                task.error_message = error_output[:500]
                logger.error(f"Conversion failed for task {task_id}: {error_output[:200]}")
            
            db.commit()
            
        except asyncio.CancelledError:
            task.status = ConversionStatus.CANCELLED
            db.commit()
            logger.info(f"Conversion cancelled for task {task_id}")
        except Exception as e:
            task.status = ConversionStatus.FAILED
            task.error_message = str(e)[:500]
            db.commit()
            logger.error(f"Unexpected error during conversion for task {task_id}: {e}", exc_info=True)
        finally:
            db.close()
            if task_id in self.active_processes:
                del self.active_processes[task_id]
            if process and process.returncode is None:
                try:
                    process.kill()
                except Exception:
                    pass
            await redis_manager.remove_from_active(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running conversion"""
        if task_id in self.active_processes:
            process = self.active_processes[task_id]
            logger.info(f"Terminating conversion process for task {task_id}")
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning(f"Process did not terminate gracefully, killing task {task_id}")
                process.kill()
            return True
        return False


conversion_service = ConversionService()
