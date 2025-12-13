"""Core exception definitions"""

from core.exceptions.base import *  # noqa
from core.exceptions.conversion_exceptions import (
    ConversionError,
    ConversionFormatError,
    ConversionProcessError,
    ConversionTimeoutError,
    ConversionResourceError,
    ConversionFileError,
    ConversionFFmpegError,
    ConversionProcessKilledError,
    ConversionQueueError,
    ConversionDatabaseError,
)

__all__ = [
    # Base exceptions
    "BaseAPIException",
    # Conversion exceptions
    "ConversionError",
    "ConversionFormatError",
    "ConversionProcessError",
    "ConversionTimeoutError",
    "ConversionResourceError",
    "ConversionFileError",
    "ConversionFFmpegError",
    "ConversionProcessKilledError",
    "ConversionQueueError",
    "ConversionDatabaseError",
]
