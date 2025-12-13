"""Validation for conversion format and parameters"""
import logging
from typing import Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)

# Supported audio and video formats
AUDIO_FORMATS = {
    "mp3": {"codec": "libmp3lame", "default_bitrate": "192k", "sample_rates": [8000, 16000, 22050, 32000, 44100, 48000, 96000, 192000]},
    "wav": {"codec": "pcm_s16le", "default_bitrate": None, "lossless": True},
    "flac": {"codec": "flac", "default_bitrate": None, "lossless": True},
    "aac": {"codec": "aac", "default_bitrate": "192k", "sample_rates": [8000, 12000, 16000, 22050, 24000, 32000, 44100, 48000]},
    "opus": {"codec": "libopus", "default_bitrate": "128k", "sample_rates": [8000, 12000, 16000, 24000, 48000]},
    "vorbis": {"codec": "libvorbis", "default_bitrate": "192k", "sample_rates": [8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000]},
    "m4a": {"codec": "aac", "default_bitrate": "192k", "container": "ipod"},
    "ogg": {"codec": "libvorbis", "default_bitrate": "192k", "container": "ogg"},
    "alac": {"codec": "alac", "default_bitrate": None, "lossless": True},
}

VIDEO_FORMATS = {
    "mp4": {"codec": "h264", "hw_encoders": ["h264_nvenc", "h264_vaapi", "h264_qsv"]},
    "webm": {"codec": "vp9", "hw_encoders": []},
    "mkv": {"codec": "h264", "hw_encoders": ["h264_nvenc", "h264_vaapi", "h264_qsv"]},
    "mov": {"codec": "prores", "hw_encoders": []},
    "avi": {"codec": "mpeg4", "hw_encoders": []},
    "flv": {"codec": "mpeg4", "hw_encoders": []},
    "hdr": {"codec": "hevc", "hw_encoders": ["hevc_nvenc", "hevc_vaapi", "hevc_qsv"]},
    "h265": {"codec": "hevc", "hw_encoders": ["hevc_nvenc", "hevc_vaapi", "hevc_qsv"]},
}

ALL_FORMATS = {**AUDIO_FORMATS, **VIDEO_FORMATS}


class ConversionValidationError(ValueError):
    """Raised when conversion parameters are invalid"""
    pass


class ConversionValidator:
    """Validates conversion format and parameters"""
    
    @staticmethod
    def validate_format(format_name: str) -> bool:
        """Check if format is supported"""
        return format_name.lower() in ALL_FORMATS
    
    @staticmethod
    def validate_bitrate(bitrate: Optional[str]) -> bool:
        """Validate bitrate format (e.g., 128k, 5M, 320000)"""
        if not bitrate:
            return True
        
        # Matches patterns like: 128k, 192K, 5M, 5m, 320000
        pattern = r'^\d+(?:\.[0-9]+)?[kKmM]?$'
        return bool(re.match(pattern, bitrate))
    
    @staticmethod
    def validate_sample_rate(sample_rate: Optional[int], target_format: str) -> bool:
        """Validate sample rate for audio format"""
        if not sample_rate:
            return True
        
        fmt = target_format.lower()
        if fmt not in AUDIO_FORMATS:
            return False
        
        fmt_info = AUDIO_FORMATS[fmt]
        if "sample_rates" not in fmt_info:
            return True  # No restriction
        
        return sample_rate in fmt_info["sample_rates"]
    
    @staticmethod
    def validate_channels(channels: Optional[int]) -> bool:
        """Validate channel count (1=mono, 2=stereo, 6=5.1, etc.)"""
        if not channels:
            return True
        return 1 <= channels <= 8
    
    @staticmethod
    def get_format_info(format_name: str) -> Dict:
        """Get detailed format information"""
        fmt = format_name.lower()
        if fmt not in ALL_FORMATS:
            raise ConversionValidationError(f"Unsupported format: {format_name}")
        return ALL_FORMATS[fmt]
    
    @staticmethod
    def is_audio_format(format_name: str) -> bool:
        """Check if format is audio-only"""
        return format_name.lower() in AUDIO_FORMATS
    
    @staticmethod
    def is_video_format(format_name: str) -> bool:
        """Check if format is video"""
        return format_name.lower() in VIDEO_FORMATS
    
    @staticmethod
    def normalize_bitrate(bitrate: str) -> str:
        """Normalize bitrate to standard format (e.g., 128k)"""
        bitrate = bitrate.strip()
        
        # Convert to number
        match = re.match(r'^([\d.]+)([kKmM]?)$', bitrate)
        if not match:
            raise ConversionValidationError(f"Invalid bitrate format: {bitrate}")
        
        value, unit = match.groups()
        value = float(value)
        
        if unit in ['M', 'm']:
            value = value * 1000
        
        return f"{int(value)}k" if value < 1000 else f"{int(value/1000)}M"
    
    @staticmethod
    def suggest_bitrate(source_bitrate: Optional[str], target_format: str) -> str:
        """Suggest appropriate bitrate for target format based on source"""
        fmt = target_format.lower()
        
        if fmt not in AUDIO_FORMATS:
            raise ConversionValidationError(f"Unsupported audio format: {target_format}")
        
        fmt_info = AUDIO_FORMATS[fmt]
        
        # If format is lossless, no bitrate needed
        if fmt_info.get("lossless"):
            return None
        
        # If source has bitrate info, use similar
        if source_bitrate:
            try:
                normalized = ConversionValidator.normalize_bitrate(source_bitrate)
                # Don't over-compress
                if target_format.lower() == "mp3" and normalized in ["32k", "64k"]:
                    return "128k"
                return normalized
            except Exception:
                pass
        
        # Use format default
        return fmt_info.get("default_bitrate", "192k")
    
    @staticmethod
    def validate_conversion_params(
        source_format: str,
        target_format: str,
        target_bitrate: Optional[str] = None,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate all conversion parameters
        
        Returns:
            (is_valid, error_message)
        """
        # Check formats
        if not ConversionValidator.validate_format(target_format):
            return False, f"Unsupported target format: {target_format}"
        
        # Check bitrate
        if target_bitrate and not ConversionValidator.validate_bitrate(target_bitrate):
            return False, f"Invalid bitrate format: {target_bitrate}"
        
        # Check sample rate
        if sample_rate and not ConversionValidator.validate_sample_rate(sample_rate, target_format):
            fmt_info = AUDIO_FORMATS.get(target_format.lower(), {})
            allowed = fmt_info.get("sample_rates", [])
            return False, f"Invalid sample rate for {target_format}: {sample_rate}. Allowed: {allowed}"
        
        # Check channels
        if channels and not ConversionValidator.validate_channels(channels):
            return False, f"Invalid channel count: {channels}. Must be 1-8"
        
        return True, None


conversion_validator = ConversionValidator()
