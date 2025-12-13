"""Comprehensive error handling for FastAPI"""
import logging
from typing import Callable, Any
from functools import wraps

from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.exceptions.conversion_exceptions import (
    ConversionError,
    ConversionTimeoutError,
    ConversionResourceError,
    ConversionFileError,
    ConversionProcessError
)
from core.logging.structured_logging import (
    get_context,
    set_correlation_id
)

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standard error response format"""
    
    @staticmethod
    def format(
        error_code: str,
        message: str,
        status_code: int,
        details: dict = None,
        correlation_id: str = None
    ) -> dict:
        """Format standardized error response
        
        Returns:
            Dict with error info
        """
        context = get_context()
        
        return {
            "error": {
                "code": error_code,
                "message": message,
                "status": status_code,
                "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
                "details": details or {},
                "correlation_id": correlation_id or context.get("correlation_id"),
                "request_id": context.get("task_id")
            }
        }


def error_handler(
    app: FastAPI
) -> None:
    """Register comprehensive error handlers"""
    
    @app.exception_handler(ConversionTimeoutError)
    async def handle_timeout_error(
        request: Request,
        exc: ConversionTimeoutError
    ) -> JSONResponse:
        logger.error(f"Conversion timeout: {exc}")
        
        return JSONResponse(
            status_code=408,
            content=ErrorResponse.format(
                error_code="CONVERSION_TIMEOUT",
                message="Conversion operation exceeded maximum time limit",
                status_code=408,
                details={"timeout_error": str(exc)}
            )
        )
    
    @app.exception_handler(ConversionResourceError)
    async def handle_resource_error(
        request: Request,
        exc: ConversionResourceError
    ) -> JSONResponse:
        logger.error(f"Resource error: {exc}")
        
        return JSONResponse(
            status_code=507,
            content=ErrorResponse.format(
                error_code="INSUFFICIENT_RESOURCES",
                message="System resources insufficient for operation",
                status_code=507,
                details={"resource_error": str(exc)}
            )
        )
    
    @app.exception_handler(ConversionFileError)
    async def handle_file_error(
        request: Request,
        exc: ConversionFileError
    ) -> JSONResponse:
        logger.error(f"File error: {exc}")
        
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.format(
                error_code="FILE_ERROR",
                message="File operation failed",
                status_code=400,
                details={"file_error": str(exc)}
            )
        )
    
    @app.exception_handler(ConversionProcessError)
    async def handle_process_error(
        request: Request,
        exc: ConversionProcessError
    ) -> JSONResponse:
        logger.error(f"Process error: {exc}")
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse.format(
                error_code="PROCESS_ERROR",
                message="Media processing failed",
                status_code=500,
                details={"process_error": str(exc)}
            )
        )
    
    @app.exception_handler(ConversionError)
    async def handle_conversion_error(
        request: Request,
        exc: ConversionError
    ) -> JSONResponse:
        logger.error(f"Conversion error: {exc}")
        
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.format(
                error_code="CONVERSION_ERROR",
                message="Conversion operation failed",
                status_code=400,
                details={"conversion_error": str(exc)}
            )
        )
    
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(f"Validation error: {exc}")
        
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(x) for x in error["loc"][1:]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        return JSONResponse(
            status_code=422,
            content=ErrorResponse.format(
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                status_code=422,
                details={"errors": errors}
            )
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException
    ) -> JSONResponse:
        logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse.format(
                error_code=f"HTTP_{exc.status_code}",
                message=exc.detail,
                status_code=exc.status_code
            )
        )
    
    @app.exception_handler(Exception)
    async def handle_general_exception(
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {exc}",
            exc_info=True
        )
        
        # Don't expose internal error details
        return JSONResponse(
            status_code=500,
            content=ErrorResponse.format(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                status_code=500
            )
        )


def safe_operation(func: Callable) -> Callable:
    """Decorator for safe API operations with error handling
    
    Wraps function with try-catch and proper error response
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            # Ensure correlation ID is set
            if hasattr(args[0], 'headers'):
                request = args[0]
                correlation_id = request.headers.get(
                    'x-correlation-id',
                    request.headers.get('x-request-id')
                )
                if correlation_id:
                    set_correlation_id(correlation_id)
            
            return await func(*args, **kwargs)
        
        except Exception as e:
            logger.error(
                f"Error in {func.__name__}: {type(e).__name__}: {e}",
                exc_info=True
            )
            raise
    
    return wrapper
