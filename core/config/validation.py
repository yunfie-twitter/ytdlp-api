"""Configuration validation and environment checks"""
import logging
import os
from typing import Tuple, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validate application configuration"""
    
    def __init__(self):
        self.errors: Dict[str, str] = {}
        self.warnings: Dict[str, str] = {}
        self.checks_passed = 0
    
    def validate_directory_exists(
        self,
        path: str,
        name: str,
        create_if_missing: bool = True
    ) -> bool:
        """Validate directory exists
        
        Returns:
            bool: True if valid
        """
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                if create_if_missing:
                    path_obj.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {path}")
                    self.checks_passed += 1
                    return True
                else:
                    self.errors[name] = f"Directory not found: {path}"
                    return False
            
            if not path_obj.is_dir():
                self.errors[name] = f"Path is not a directory: {path}"
                return False
            
            # Check if writable
            if not os.access(path, os.W_OK):
                self.errors[name] = f"Directory is not writable: {path}"
                return False
            
            self.checks_passed += 1
            return True
        
        except Exception as e:
            self.errors[name] = f"Error checking directory: {e}"
            return False
    
    def validate_environment_variable(
        self,
        var_name: str,
        required: bool = True,
        allowed_values: list = None
    ) -> bool:
        """Validate environment variable
        
        Returns:
            bool: True if valid
        """
        value = os.getenv(var_name)
        
        if not value:
            if required:
                self.errors[var_name] = f"Required environment variable not set"
                return False
            self.checks_passed += 1
            return True
        
        if allowed_values and value not in allowed_values:
            self.errors[var_name] = (
                f"Invalid value '{value}'. Allowed: {', '.join(allowed_values)}"
            )
            return False
        
        self.checks_passed += 1
        return True
    
    def validate_file_exists(
        self,
        path: str,
        name: str,
        required: bool = True
    ) -> bool:
        """Validate file exists
        
        Returns:
            bool: True if valid
        """
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                if required:
                    self.errors[name] = f"File not found: {path}"
                    return False
                self.checks_passed += 1
                return True
            
            if not path_obj.is_file():
                self.errors[name] = f"Path is not a file: {path}"
                return False
            
            self.checks_passed += 1
            return True
        
        except Exception as e:
            self.errors[name] = f"Error checking file: {e}"
            return False
    
    def validate_integer(
        self,
        name: str,
        value: Any,
        min_val: int = None,
        max_val: int = None
    ) -> bool:
        """Validate integer configuration value
        
        Returns:
            bool: True if valid
        """
        try:
            int_val = int(value)
            
            if min_val is not None and int_val < min_val:
                self.errors[name] = f"Value {int_val} is less than minimum {min_val}"
                return False
            
            if max_val is not None and int_val > max_val:
                self.errors[name] = f"Value {int_val} is greater than maximum {max_val}"
                return False
            
            self.checks_passed += 1
            return True
        
        except ValueError:
            self.errors[name] = f"Value '{value}' is not a valid integer"
            return False
    
    def validate_url(
        self,
        name: str,
        url: str
    ) -> bool:
        """Validate URL format
        
        Returns:
            bool: True if valid
        """
        try:
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            
            if not parsed.scheme or not parsed.netloc:
                self.errors[name] = f"Invalid URL format: {url}"
                return False
            
            self.checks_passed += 1
            return True
        
        except Exception as e:
            self.errors[name] = f"Error validating URL: {e}"
            return False
    
    def validate_executable(
        self,
        name: str,
        executable_path: str
    ) -> bool:
        """Validate executable file exists and is runnable
        
        Returns:
            bool: True if valid
        """
        try:
            # Try to find executable in PATH
            result = os.system(f"which {executable_path} > /dev/null 2>&1") == 0
            
            if result:
                self.checks_passed += 1
                logger.info(f"Executable found: {executable_path}")
                return True
            else:
                self.errors[name] = f"Executable not found in PATH: {executable_path}"
                return False
        
        except Exception as e:
            self.errors[name] = f"Error checking executable: {e}"
            return False
    
    def get_validation_report(self) -> Dict:
        """Get validation report
        
        Returns:
            Dict with validation results
        """
        return {
            "passed": self.checks_passed,
            "errors": dict(self.errors) if self.errors else None,
            "warnings": dict(self.warnings) if self.warnings else None,
            "is_valid": len(self.errors) == 0
        }
    
    def log_report(self) -> None:
        """Log validation report"""
        report = self.get_validation_report()
        
        logger.info(
            f"Configuration validation: {report['passed']} checks passed"
        )
        
        for name, error in self.errors.items():
            logger.error(f"  ✗ {name}: {error}")
        
        for name, warning in self.warnings.items():
            logger.warning(f"  ⚠ {name}: {warning}")
        
        if report["is_valid"]:
            logger.info("✓ All configuration checks passed")
        else:
            logger.critical("✗ Configuration validation failed")


def validate_application_config() -> Tuple[bool, Dict]:
    """Validate complete application configuration
    
    Returns:
        (is_valid, report)
    """
    validator = ConfigValidator()
    
    # Check required directories
    from core.config import settings
    
    validator.validate_directory_exists(
        settings.DOWNLOAD_DIR,
        "DOWNLOAD_DIR",
        create_if_missing=True
    )
    
    # Check required environment variables
    validator.validate_environment_variable("DATABASE_URL", required=True)
    validator.validate_environment_variable("REDIS_URL", required=True)
    
    # Check ffmpeg executable
    validator.validate_executable("ffmpeg", "ffmpeg")
    
    # Get report
    report = validator.get_validation_report()
    validator.log_report()
    
    return report["is_valid"], report
