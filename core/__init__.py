"""Core package - configuration, security, exceptions, and validation"""

# Configuration
from core.config import settings

# Authentication & Security
from core.auth import (
    jwt_auth,
    JWTAuth,
    check_rate_limit,
    set_redis_manager,
    verify_api_key,
    get_optional_api_key,
    is_feature_enabled
)

# Exceptions
from core.exceptions import (
    APIException,
    ValidationError,
    InvalidURLError,
    InvalidUUIDError,
    InvalidFormatError,
    InvalidLanguageCodeError,
    NotFoundError,
    TaskNotFoundError,
    FileNotFoundError,
    DownloadError,
    DownloadTimeoutError,
    VideoInfoError,
    QueueError,
    TaskNotCancellableError,
    ExternalServiceError,
    RedisError,
    DatabaseError,
    YtDlpError,
    RateLimitError,
    TimeoutError as TimeoutErrorException,
    InvalidStateError,
    FileAccessError,
    PathTraversalError,
    DiskSpaceError,
    ConflictError,
    InternalServerError
)

# Error Handling
from core.error_handling import (
    ErrorContext,
    RetryConfig,
    async_error_handler,
    sync_error_handler,
    async_retry,
    sync_retry,
    log_error_summary,
    CodeAnalyzer,
    DocumentationAnalyzer,
    StyleChecker,
    RefactoringHelper,
    MetricsCollector,
    metrics_collector
)

# Validation
from core.validation import (
    URLValidator,
    UUIDValidator,
    LanguageCodeValidator,
    FormatValidator,
    QualityValidator,
    LimitValidator,
    InputValidator
)

# Logging
from core.logging import (
    setup_logging,
    PerformanceLogger,
    JSONFormatter,
    LoggingMiddleware
)

# Caching
from core.cache import CacheManager, cache_manager

# Database
from core.database import (
    QueryCache,
    IndexAnalyzer,
    BulkOperationOptimizer,
    ConnectionPoolOptimizer,
    query_cache,
    RateLimiter,
    rate_limiter
)

# Monitoring
from core.monitoring import (
    HealthStatus,
    HealthCheckComponent,
    HealthMonitor,
    health_monitor
)

# Performance
from core.performance import (
    PerformanceMonitor,
    ProfileDecorator,
    ConcurrencyOptimizer,
    MemoryOptimizer,
    QueryOptimizer,
    performance_monitor,
    profile
)

__all__ = [
    # Configuration
    'settings',
    # Authentication & Security
    'jwt_auth',
    'JWTAuth',
    'check_rate_limit',
    'set_redis_manager',
    'verify_api_key',
    'get_optional_api_key',
    'is_feature_enabled',
    # Exceptions
    'APIException',
    'ValidationError',
    'InvalidURLError',
    'InvalidUUIDError',
    'InvalidFormatError',
    'InvalidLanguageCodeError',
    'NotFoundError',
    'TaskNotFoundError',
    'FileNotFoundError',
    'DownloadError',
    'DownloadTimeoutError',
    'VideoInfoError',
    'QueueError',
    'TaskNotCancellableError',
    'ExternalServiceError',
    'RedisError',
    'DatabaseError',
    'YtDlpError',
    'RateLimitError',
    'TimeoutErrorException',
    'InvalidStateError',
    'FileAccessError',
    'PathTraversalError',
    'DiskSpaceError',
    'ConflictError',
    'InternalServerError',
    # Error Handling
    'ErrorContext',
    'RetryConfig',
    'async_error_handler',
    'sync_error_handler',
    'async_retry',
    'sync_retry',
    'log_error_summary',
    'CodeAnalyzer',
    'DocumentationAnalyzer',
    'StyleChecker',
    'RefactoringHelper',
    'MetricsCollector',
    'metrics_collector',
    # Validation
    'URLValidator',
    'UUIDValidator',
    'LanguageCodeValidator',
    'FormatValidator',
    'QualityValidator',
    'LimitValidator',
    'InputValidator',
    # Logging
    'setup_logging',
    'PerformanceLogger',
    'JSONFormatter',
    'LoggingMiddleware',
    # Caching
    'CacheManager',
    'cache_manager',
    # Database
    'QueryCache',
    'IndexAnalyzer',
    'BulkOperationOptimizer',
    'ConnectionPoolOptimizer',
    'query_cache',
    'RateLimiter',
    'rate_limiter',
    # Monitoring
    'HealthStatus',
    'HealthCheckComponent',
    'HealthMonitor',
    'health_monitor',
    # Performance
    'PerformanceMonitor',
    'ProfileDecorator',
    'ConcurrencyOptimizer',
    'MemoryOptimizer',
    'QueryOptimizer',
    'performance_monitor',
    'profile'
]
