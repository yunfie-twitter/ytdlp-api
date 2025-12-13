"""Custom exceptions for conversion operations"""


class ConversionError(Exception):
    """Base exception for conversion errors"""
    pass


class ConversionFormatError(ConversionError):
    """Raised when format is unsupported or invalid"""
    pass


class ConversionProcessError(ConversionError):
    """Raised when ffmpeg process fails"""
    pass


class ConversionTimeoutError(ConversionError):
    """Raised when conversion exceeds timeout"""
    pass


class ConversionResourceError(ConversionError):
    """Raised when system resources are insufficient"""
    pass


class ConversionFileError(ConversionError):
    """Raised when file operations fail"""
    pass


class ConversionFFmpegError(ConversionProcessError):
    """Raised when ffmpeg execution fails"""
    def __init__(self, message: str, returncode: int = None, stderr: str = None):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class ConversionProcessKilledError(ConversionProcessError):
    """Raised when conversion process is killed/terminated"""
    pass


class ConversionQueueError(ConversionError):
    """Raised when queue operations fail"""
    pass


class ConversionDatabaseError(ConversionError):
    """Raised when database operations fail"""
    pass
