"""Enhanced ffmpeg process management with resource monitoring and graceful handling"""
import asyncio
import logging
import os
import signal
import psutil
from typing import Optional, Dict
from pathlib import Path
from datetime import datetime, timedelta

from core.config import settings
from core.exceptions.conversion_exceptions import (
    ConversionProcessError,
    ConversionTimeoutError,
    ConversionProcessKilledError,
    ConversionResourceError
)

logger = logging.getLogger(__name__)


class FFmpegProcessManager:
    """Manages ffmpeg processes with resource monitoring and graceful termination"""
    
    # Resource limits
    MAX_MEMORY_MB = getattr(settings, "FFMPEG_MAX_MEMORY_MB", 2048)
    MAX_CPU_PERCENT = getattr(settings, "FFMPEG_MAX_CPU_PERCENT", 95)
    PROCESS_TIMEOUT = getattr(settings, "FFMPEG_TIMEOUT", 14400)  # 4 hours
    
    def __init__(self):
        self.active_processes: Dict[str, dict] = {}
        self.process_stats: Dict[str, dict] = {}
    
    def _monitor_process_resources(self, pid: int, task_id: str) -> bool:
        """Monitor process resources and return True if within limits
        
        Returns:
            bool: True if resources within limits, False if exceeded
        """
        try:
            process = psutil.Process(pid)
            
            # Get memory usage
            memory_mb = process.memory_info().rss / (1024 * 1024)
            
            # Get CPU usage
            cpu_percent = process.cpu_percent(interval=0.1)
            
            # Store stats
            if task_id not in self.process_stats:
                self.process_stats[task_id] = {
                    "max_memory_mb": 0,
                    "max_cpu_percent": 0,
                    "start_time": datetime.utcnow()
                }
            
            stats = self.process_stats[task_id]
            stats["max_memory_mb"] = max(stats.get("max_memory_mb", 0), memory_mb)
            stats["max_cpu_percent"] = max(stats.get("max_cpu_percent", 0), cpu_percent)
            
            # Check limits
            if memory_mb > self.MAX_MEMORY_MB:
                logger.error(
                    f"Process {pid} (task {task_id}) exceeded memory limit: "
                    f"{memory_mb:.1f}MB > {self.MAX_MEMORY_MB}MB"
                )
                return False
            
            if cpu_percent > self.MAX_CPU_PERCENT:
                logger.warning(
                    f"Process {pid} (task {task_id}) high CPU usage: {cpu_percent:.1f}% "
                    f"(limit: {self.MAX_CPU_PERCENT}%)"
                )
            
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Could not monitor process {pid}: {e}")
            return True  # Allow process to continue
    
    async def execute_with_monitoring(
        self,
        cmd: list,
        task_id: str,
        stdin=None,
        stdout=None,
        stderr=None
    ) -> tuple:
        """Execute ffmpeg with resource monitoring
        
        Returns:
            (process, stdout_iter, stderr_iter)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr
            )
            
            self.active_processes[task_id] = {
                "process": process,
                "pid": process.pid,
                "start_time": datetime.utcnow(),
                "cmd": " ".join(cmd)
            }
            
            logger.info(f"Process {process.pid} started for task {task_id}")
            
            return process
        
        except Exception as e:
            logger.error(f"Failed to start ffmpeg process for task {task_id}: {e}")
            raise ConversionProcessError(f"Failed to start ffmpeg: {e}")
    
    async def wait_with_timeout(
        self,
        process: asyncio.subprocess.Process,
        task_id: str,
        timeout: Optional[int] = None
    ) -> int:
        """Wait for process with timeout and resource monitoring
        
        Returns:
            Process return code
        """
        timeout = timeout or self.PROCESS_TIMEOUT
        
        try:
            # Monitor every 10 seconds
            while True:
                try:
                    return_code = await asyncio.wait_for(
                        process.wait(),
                        timeout=10
                    )
                    return return_code
                
                except asyncio.TimeoutError:
                    # Check resources
                    if not self._monitor_process_resources(process.pid, task_id):
                        await self.terminate_process(process, task_id, force=True)
                        raise ConversionResourceError(
                            f"Process exceeded resource limits (task: {task_id})"
                        )
                    
                    # Check overall timeout
                    elapsed = (datetime.utcnow() - self.active_processes[task_id]["start_time"]).total_seconds()
                    if elapsed > timeout:
                        await self.terminate_process(process, task_id, force=True)
                        raise ConversionTimeoutError(
                            f"Process exceeded timeout of {timeout}s (task: {task_id})"
                        )
                    
                    # Continue waiting
                    continue
        
        except ConversionTimeoutError:
            raise
        except ConversionResourceError:
            raise
        except Exception as e:
            logger.error(f"Error waiting for process {process.pid}: {e}")
            raise ConversionProcessError(f"Error waiting for process: {e}")
    
    async def terminate_process(
        self,
        process: asyncio.subprocess.Process,
        task_id: str,
        force: bool = False
    ) -> bool:
        """Gracefully terminate process with optional force kill
        
        Returns:
            bool: True if successfully terminated
        """
        try:
            if not force:
                # Try graceful termination first
                logger.info(f"Terminating process {process.pid} (task {task_id}) gracefully")
                process.terminate()
                
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                    logger.info(f"Process {process.pid} terminated gracefully")
                    return True
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Process {process.pid} did not terminate gracefully, "
                        f"will force kill"
                    )
                    force = True
            
            if force:
                logger.info(f"Force killing process {process.pid} (task {task_id})")
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                    logger.info(f"Process {process.pid} force killed")
                    return True
                except asyncio.TimeoutError:
                    logger.error(f"Failed to kill process {process.pid}")
                    return False
        
        except Exception as e:
            logger.error(f"Error terminating process {process.pid}: {e}")
            return False
        
        finally:
            if task_id in self.active_processes:
                del self.active_processes[task_id]
    
    def get_process_stats(self, task_id: str) -> Optional[dict]:
        """Get resource statistics for a task"""
        return self.process_stats.get(task_id)
    
    def cleanup_stats(self, task_id: str):
        """Clean up statistics for completed task"""
        if task_id in self.process_stats:
            del self.process_stats[task_id]
    
    def get_active_processes(self) -> int:
        """Get count of active processes"""
        return len(self.active_processes)


ffmpeg_process_manager = FFmpegProcessManager()
