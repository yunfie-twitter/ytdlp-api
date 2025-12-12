"""Input validation utilities"""
import re
import logging
from typing import Optional, List
from urllib.parse import urlparse
import uuid as uuid_lib

from core.exceptions import (
    InvalidURLError,
    InvalidUUIDError,
    InvalidLanguageCodeError,
    InvalidFormatError
)

logger = logging.getLogger(__name__)

class URLValidator:
    """URL validation utilities"""
    
    VALID_SCHEMES = ('http', 'https')
    
    @staticmethod
    def validate(url: str) -> bool:
        """Validate URL format"""
        if not url or not isinstance(url, str):
            return False
        
        try:
            result = urlparse(url)
            return (
                result.scheme in URLValidator.VALID_SCHEMES and
                bool(result.netloc) and
                len(url) <= 2048  # URL length limit
            )
        except Exception:
            return False
    
    @staticmethod
    def validate_or_raise(url: str) -> str:
        """Validate URL and raise exception if invalid"""
        if not URLValidator.validate(url):
            raise InvalidURLError(url)
        return url

class UUIDValidator:
    """UUID validation utilities"""
    
    @staticmethod
    def validate(uuid_str: str) -> bool:
        """Validate UUID format"""
        try:
            uuid_lib.UUID(uuid_str)
            return True
        except (ValueError, AttributeError, TypeError):
            return False
    
    @staticmethod
    def validate_or_raise(uuid_str: str) -> str:
        """Validate UUID and raise exception if invalid"""
        if not UUIDValidator.validate(uuid_str):
            raise InvalidUUIDError(uuid_str)
        return uuid_str

class LanguageCodeValidator:
    """Language code validation utilities"""
    
    # RFC 5646 language tag pattern (simplified)
    PATTERN = re.compile(r'^[a-z]{2}(-[A-Z]{2})?$')
    
    @staticmethod
    def validate(lang: str) -> bool:
        """Validate language code format"""
        return bool(LanguageCodeValidator.PATTERN.match(lang)) if lang else False
    
    @staticmethod
    def validate_or_raise(lang: str) -> str:
        """Validate language code and raise exception if invalid"""
        if not LanguageCodeValidator.validate(lang):
            raise InvalidLanguageCodeError(lang)
        return lang

class FormatValidator:
    """Format validation utilities"""
    
    ALLOWED_FORMATS = {
        'mp3': 'MP3 Audio',
        'mp4': 'MP4 Video',
        'best': 'Best Format',
        'audio': 'Best Audio',
        'video': 'Best Video',
        'webm': 'WebM Format',
        'wav': 'WAV Audio',
        'flac': 'FLAC Audio',
        'aac': 'AAC Audio'
    }
    
    @staticmethod
    def validate(format_type: str) -> bool:
        """Validate format type"""
        return format_type and format_type.lower() in FormatValidator.ALLOWED_FORMATS
    
    @staticmethod
    def validate_or_raise(format_type: str) -> str:
        """Validate format and raise exception if invalid"""
        if not FormatValidator.validate(format_type):
            raise InvalidFormatError(
                format_type,
                list(FormatValidator.ALLOWED_FORMATS.keys())
            )
        return format_type.lower()
    
    @staticmethod
    def get_descriptions() -> dict:
        """Get format descriptions"""
        return FormatValidator.ALLOWED_FORMATS.copy()

class QualityValidator:
    """Quality parameter validation utilities"""
    
    VALID_QUALITIES = {'best', 'worst'}
    QUALITY_PATTERN = re.compile(r'^\d{3,4}p$')  # e.g., 1080p, 480p
    
    @staticmethod
    def validate(quality: str) -> bool:
        """Validate quality parameter"""
        if not quality:
            return True  # Quality is optional
        
        quality_lower = quality.lower()
        return (
            quality_lower in QualityValidator.VALID_QUALITIES or
            bool(QualityValidator.QUALITY_PATTERN.match(quality))
        )
    
    @staticmethod
    def validate_or_raise(quality: str) -> Optional[str]:
        """Validate quality and raise exception if invalid, fallback to 'best' if not provided"""
        # If quality is not provided or empty, use default 'best'
        if not quality:
            return 'best'
        
        # Validate the provided quality
        if not QualityValidator.validate(quality):
            # Log warning and fallback to 'best'
            logger.warning(f"Invalid quality '{quality}', falling back to 'best'")
            return 'best'
        
        return quality

class LimitValidator:
    """Limit parameter validation utilities"""
    
    MIN_LIMIT = 1
    MAX_LIMIT = 200
    DEFAULT_LIMIT = 50
    
    @staticmethod
    def validate(limit: int) -> bool:
        """Validate limit parameter"""
        return isinstance(limit, int) and LimitValidator.MIN_LIMIT <= limit <= LimitValidator.MAX_LIMIT
    
    @staticmethod
    def validate_and_clamp(limit: int) -> int:
        """Validate and clamp limit to valid range"""
        if not isinstance(limit, int):
            return LimitValidator.DEFAULT_LIMIT
        return max(LimitValidator.MIN_LIMIT, min(limit, LimitValidator.MAX_LIMIT))

class InputValidator:
    """Combined input validation helper"""
    
    @staticmethod
    def validate_download_request(
        url: str,
        format_type: str,
        quality: Optional[str] = None,
        mp3_title: Optional[str] = None
    ) -> tuple[str, str, Optional[str]]:
        """Validate all download request parameters"""
        # Validate URL
        url = URLValidator.validate_or_raise(url)
        
        # Validate format
        format_type = FormatValidator.validate_or_raise(format_type)
        
        # Validate quality
        quality = QualityValidator.validate_or_raise(quality)
        
        # Validate MP3 title length
        if mp3_title and len(mp3_title) > 1000:
            mp3_title = mp3_title[:1000]
        
        return url, format_type, quality
    
    @staticmethod
    def validate_info_request(url: str) -> str:
        """Validate info request parameters"""
        return URLValidator.validate_or_raise(url)
    
    @staticmethod
    def validate_subtitle_request(
        url: str,
        lang: str = 'en'
    ) -> tuple[str, str]:
        """Validate subtitle request parameters"""
        url = URLValidator.validate_or_raise(url)
        lang = LanguageCodeValidator.validate_or_raise(lang)
        return url, lang
    
    @staticmethod
    def validate_task_id(task_id: str) -> str:
        """Validate task ID"""
        return UUIDValidator.validate_or_raise(task_id)
