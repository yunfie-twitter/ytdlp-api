"""Core package - configuration, security, exceptions, and validation"""
from core.config import settings
from core.security import (
    check_rate_limit,
    set_redis_manager,
    verify_api_key,
    get_optional_api_key,
    is_feature_enabled
)
from core.jwt_auth import jwt_auth
from core.exceptions import (
    APIException,
    ValidationError,
    InvalidURLError,
    InvalidUUIDError,
    InvalidFormatError,
    TaskNotFoundError,
    DownloadError,
    DownloadTimeoutError,
    VideoInfoError,
    RateLimitError,
    TimeoutError as TimeoutErrorException,
    InvalidStateError,
    FileAccessError,
    PathTraversalError,
    DiskSpaceError,
    InternalServerError
)
from core.error_handler import (
    ErrorContext,
    async_error_handler,
    sync_error_handler,
    RetryConfig,
    async_retry,
    sync_retry,
    log_error_summary
)
from core.validation import (
    URLValidator,
    UUIDValidator,
    LanguageCodeValidator,
    FormatValidator,
    QualityValidator,
    LimitValidator,
    InputValidator
)

__all__ = [
    'settings',
    'check_rate_limit',
    'set_redis_manager',
    'verify_api_key',
    'get_optional_api_key',
    'is_feature_enabled',
    'jwt_auth',
    'APIException',
    'ValidationError',
    'InvalidURLError',
    'InvalidUUIDError',
    'InvalidFormatError',
    'TaskNotFoundError',
    'DownloadError',
    'DownloadTimeoutError',
    'VideoInfoError',
    'RateLimitError',
    'TimeoutErrorException',
    'InvalidStateError',
    'FileAccessError',
    'PathTraversalError',
    'DiskSpaceError',
    'InternalServerError',
    'ErrorContext',
    'async_error_handler',
    'sync_error_handler',
    'RetryConfig',
    'async_retry',
    'sync_retry',
    'log_error_summary',
    'URLValidator',
    'UUIDValidator',
    'LanguageCodeValidator',
    'FormatValidator',
    'QualityValidator',
    'LimitValidator',
    'InputValidator'
]
