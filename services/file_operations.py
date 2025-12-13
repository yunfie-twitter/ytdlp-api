"""Safe and robust file operations with validation and recovery"""
import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Optional, Tuple
import aiofiles
import aiofiles.os

from core.config import settings
from core.exceptions.conversion_exceptions import ConversionFileError

logger = logging.getLogger(__name__)


class FileOperationManager:
    """Manages file operations with safety checks and recovery"""
    
    def __init__(self):
        self.download_dir = Path(settings.DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = getattr(settings, "MAX_FILE_SIZE", 100 * 1024 * 1024 * 1024)  # 100GB
        self.safe_extensions = {
            # Audio
            'mp3', 'wav', 'flac', 'aac', 'opus', 'ogg', 'm4a', 'alac',
            # Video
            'mp4', 'webm', 'mkv', 'mov', 'avi', 'flv', 'h265', 'hevc'
        }
    
    async def verify_source_file(
        self,
        file_path: str,
        min_size: int = 1024
    ) -> Tuple[bool, Optional[str]]:
        """Verify source file exists, is readable, and has minimum size
        
        Returns:
            (is_valid, error_message)
        """
        try:
            path = Path(file_path)
            
            # Check if file exists
            if not path.exists():
                return False, f"Source file not found: {file_path}"
            
            # Check if it's a file (not directory)
            if not path.is_file():
                return False, f"Path is not a file: {file_path}"
            
            # Check if readable
            if not path.stat().st_mode & 0o400:
                return False, f"Source file is not readable: {file_path}"
            
            # Check file size
            file_size = path.stat().st_size
            if file_size < min_size:
                return False, f"File too small ({file_size} bytes < {min_size} bytes)"
            
            if file_size > self.max_file_size:
                return False, f"File too large ({file_size} bytes > {self.max_file_size} bytes)"
            
            return True, None
        
        except Exception as e:
            return False, f"Error verifying file: {e}"
    
    async def verify_output_directory(
        self,
        directory: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Verify output directory is writable
        
        Returns:
            (is_valid, error_message)
        """
        try:
            output_dir = Path(directory or settings.DOWNLOAD_DIR)
            
            # Try to create if doesn't exist
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if writable
            if not output_dir.stat().st_mode & 0o200:
                return False, f"Output directory is not writable: {output_dir}"
            
            return True, None
        
        except Exception as e:
            return False, f"Error verifying output directory: {e}"
    
    async def get_safe_output_path(
        self,
        task_id: str,
        target_format: str,
        output_dir: Optional[str] = None
    ) -> Tuple[Path, Optional[str]]:
        """Get a safe output file path
        
        Returns:
            (output_path, error_message)
        """
        try:
            output_directory = Path(output_dir or settings.DOWNLOAD_DIR)
            
            # Validate format extension
            ext = target_format.lower().strip('.')
            if ext not in self.safe_extensions:
                return None, f"Unsafe file extension: {ext}"
            
            # Construct safe filename
            output_filename = f"{task_id}.{ext}"
            output_path = output_directory / output_filename
            
            # Check for path traversal attempts
            try:
                output_path.resolve().relative_to(output_directory.resolve())
            except ValueError:
                return None, f"Path traversal detected in output path"
            
            return output_path, None
        
        except Exception as e:
            return None, f"Error getting output path: {e}"
    
    async def safe_delete_file(
        self,
        file_path: str,
        verify_in_download_dir: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Safely delete a file with path verification
        
        Returns:
            (success, error_message)
        """
        try:
            path = Path(file_path)
            
            # Verify file is within download directory
            if verify_in_download_dir:
                try:
                    path.resolve().relative_to(self.download_dir.resolve())
                except ValueError:
                    return False, f"File outside download directory: {file_path}"
            
            if path.exists():
                # Try async delete
                try:
                    await aiofiles.os.remove(str(path))
                    logger.debug(f"Deleted file: {path.name}")
                except Exception:
                    # Fallback to sync delete
                    path.unlink()
                    logger.debug(f"Deleted file (sync): {path.name}")
            
            return True, None
        
        except Exception as e:
            return False, f"Error deleting file: {e}"
    
    async def calculate_file_hash(
        self,
        file_path: str,
        algorithm: str = "sha256",
        chunk_size: int = 65536
    ) -> Tuple[Optional[str], Optional[str]]:
        """Calculate file hash for integrity checking
        
        Returns:
            (hash_value, error_message)
        """
        try:
            hasher = hashlib.new(algorithm)
            
            async with aiofiles.open(file_path, 'rb') as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            
            return hasher.hexdigest(), None
        
        except Exception as e:
            return None, f"Error calculating hash: {e}"
    
    async def verify_file_integrity(
        self,
        file_path: str,
        expected_hash: Optional[str] = None,
        min_size: int = 1024
    ) -> Tuple[bool, Optional[str]]:
        """Verify file integrity and size
        
        Returns:
            (is_valid, error_message)
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return False, f"Output file not found: {file_path}"
            
            # Check size
            file_size = path.stat().st_size
            if file_size < min_size:
                return False, f"Output file too small: {file_size} bytes"
            
            # Verify hash if provided
            if expected_hash:
                actual_hash, error = await self.calculate_file_hash(file_path)
                if error:
                    return False, error
                
                if actual_hash.lower() != expected_hash.lower():
                    return False, f"Hash mismatch: {actual_hash} != {expected_hash}"
            
            return True, None
        
        except Exception as e:
            return False, f"Error verifying integrity: {e}"
    
    async def cleanup_partial_file(
        self,
        file_path: str
    ) -> Tuple[bool, Optional[str]]:
        """Clean up incomplete/partial files
        
        Returns:
            (success, error_message)
        """
        try:
            path = Path(file_path)
            
            if path.exists():
                # Create backup with .partial extension
                backup_path = path.parent / f"{path.name}.partial.bak"
                try:
                    path.rename(backup_path)
                    logger.info(f"Moved partial file to backup: {backup_path.name}")
                    
                    # Try to delete backup after a delay
                    await asyncio.sleep(1)
                    await aiofiles.os.remove(str(backup_path))
                    logger.debug(f"Deleted partial file backup: {backup_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to backup partial file: {e}")
            
            return True, None
        
        except Exception as e:
            return False, f"Error cleaning up partial file: {e}"
    
    def is_file_in_download_dir(self, file_path: str) -> bool:
        """Check if file is within download directory"""
        try:
            path = Path(file_path).resolve()
            download_dir = self.download_dir.resolve()
            path.relative_to(download_dir)
            return True
        except ValueError:
            return False


file_operation_manager = FileOperationManager()
