"""Enhanced input validation with security checks"""
import logging
import re
from typing import Tuple, Optional
from pathlib import Path

from core.config import settings
from core.exceptions.conversion_exceptions import ConversionFormatError

logger = logging.getLogger(__name__)


class EnhancedInputValidator:
    """Comprehensive input validation with security focus"""
    
    # Regex patterns for validation
    TASK_ID_PATTERN = r'^[a-f0-9\-]{36}$'  # UUID format
    FILENAME_PATTERN = r'^[a-zA-Z0-9._\-]{1,255}$'
    BITRATE_PATTERN = r'^\d+(?:\.[0-9]+)?[kKmM]?$'
    PATH_PATTERN = r'^[^<>:"|?*\x00-\x1f]*$'  # Invalid Windows/Unix path chars
    
    def __init__(self):
        self.max_path_length = 512
        self.max_title_length = 256
        self.max_error_message_length = 500
    
    def validate_task_id(self, task_id: str) -> Tuple[bool, Optional[str]]:
        """Validate task ID format (UUID)
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(task_id, str):
            return False, "Task ID must be a string"
        
        if not re.match(self.TASK_ID_PATTERN, task_id):
            return False, "Invalid task ID format"
        
        return True, None
    
    def validate_file_path(
        self,
        file_path: str,
        must_exist: bool = False,
        must_be_file: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Validate file path for security and existence
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(file_path, str):
            return False, "File path must be a string"
        
        # Check length
        if len(file_path) > self.max_path_length:
            return False, f"Path too long (>{self.max_path_length} chars)"
        
        # Check for path traversal attempts
        if ".." in file_path or file_path.startswith("~"):
            return False, "Path traversal detected"
        
        # Check for invalid characters
        if not re.match(self.PATH_PATTERN, file_path):
            return False, "Path contains invalid characters"
        
        # Try to parse as Path
        try:
            path = Path(file_path)
        except (ValueError, TypeError) as e:
            return False, f"Invalid path format: {e}"
        
        # Check existence if required
        if must_exist and not path.exists():
            return False, "File path does not exist"
        
        # Check if it's a file if required
        if must_be_file and path.exists() and not path.is_file():
            return False, "Path is not a file"
        
        return True, None
    
    def validate_filename(
        self,
        filename: str,
        allow_extension: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Validate filename format
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(filename, str):
            return False, "Filename must be a string"
        
        # Check length
        if len(filename) == 0 or len(filename) > 255:
            return False, "Filename length invalid (1-255 chars)"
        
        # Check for invalid names
        if filename in [".", "..", "CON", "PRN", "AUX", "NUL"]:
            return False, "Filename is reserved"
        
        # Check pattern
        if not re.match(self.FILENAME_PATTERN, filename):
            return False, "Filename contains invalid characters"
        
        return True, None
    
    def validate_url(
        self,
        url: str,
        max_length: int = 2048
    ) -> Tuple[bool, Optional[str]]:
        """Validate URL format
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(url, str):
            return False, "URL must be a string"
        
        # Check length
        if len(url) == 0 or len(url) > max_length:
            return False, f"URL length invalid (1-{max_length} chars)"
        
        # Check for basic URL format
        if not url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"
        
        # Validate URL structure
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc:
                return False, "URL has no domain"
        except Exception as e:
            return False, f"Invalid URL format: {e}"
        
        return True, None
    
    def validate_string_length(
        self,
        value: str,
        min_length: int = 0,
        max_length: int = 1000,
        field_name: str = "Value"
    ) -> Tuple[bool, Optional[str]]:
        """Validate string length
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(value, str):
            return False, f"{field_name} must be a string"
        
        if len(value) < min_length:
            return False, f"{field_name} too short (min {min_length} chars)"
        
        if len(value) > max_length:
            return False, f"{field_name} too long (max {max_length} chars)"
        
        return True, None
    
    def validate_integer_range(
        self,
        value: int,
        min_val: int = 0,
        max_val: int = 100,
        field_name: str = "Value"
    ) -> Tuple[bool, Optional[str]]:
        """Validate integer is within range
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(value, int):
            return False, f"{field_name} must be an integer"
        
        if value < min_val:
            return False, f"{field_name} too low (min {min_val})"
        
        if value > max_val:
            return False, f"{field_name} too high (max {max_val})"
        
        return True, None
    
    def sanitize_error_message(self, error: str) -> str:
        """Sanitize error message for external exposure
        
        Returns:
            Sanitized error message (limited length, no sensitive info)
        """
        if not isinstance(error, str):
            return "Unknown error"
        
        # Remove sensitive paths
        error = error.replace(settings.DOWNLOAD_DIR, "[DOWNLOAD_DIR]")
        
        # Truncate length
        if len(error) > self.max_error_message_length:
            error = error[:self.max_error_message_length] + "..."
        
        return error
    
    def validate_conversion_params(
        self,
        source_format: str,
        target_format: str,
        title: Optional[str] = None,
        source_file_path: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Comprehensive conversion parameter validation
        
        Returns:
            (is_valid, error_message)
        """
        # Validate formats
        if not isinstance(source_format, str) or not isinstance(target_format, str):
            return False, "Formats must be strings"
        
        if len(source_format.strip()) == 0 or len(target_format.strip()) == 0:
            return False, "Format cannot be empty"
        
        # Validate title if provided
        if title is not None:
            is_valid, error = self.validate_string_length(
                title,
                min_length=0,
                max_length=self.max_title_length,
                field_name="Title"
            )
            if not is_valid:
                return False, error
        
        # Validate file path if provided
        if source_file_path is not None:
            is_valid, error = self.validate_file_path(
                source_file_path,
                must_exist=False
            )
            if not is_valid:
                return False, error
        
        return True, None


# Global instance
enhanced_validator = EnhancedInputValidator()
