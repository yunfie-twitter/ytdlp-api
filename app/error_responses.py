"""FastAPI error response handlers"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.exceptions import APIException, InternalServerError
from core import log_error_summary

logger = logging.getLogger(__name__)

def register_exception_handlers(app: FastAPI):
    """Register all exception handlers with the FastAPI app"""
    
    # Handle custom APIException
    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        """Handle custom API exceptions"""
        logger.warning(f"API Error [{exc.error_code}]: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict()
        )
    
    # Handle validation errors
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors"""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(x) for x in error["loc"][1:]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        logger.warning(f"Validation error at {request.url.path}: {errors}")
        
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "status_code": 422,
                "details": {"errors": errors}
            }
        )
    
    # Handle HTTP exceptions
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle standard HTTP exceptions"""
        logger.warning(f"HTTP Error [{exc.status_code}]: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )
    
    # Handle all other exceptions
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        # Log detailed error summary with context
        error_context = f"Path: {request.url.path} | Method: {request.method}"
        error_summary = log_error_summary(exc, error_context)
        logger.error(f"Unexpected error: {error_summary}")
        
        # Create user-friendly response
        internal_error = InternalServerError(
            f"An unexpected error occurred: {type(exc).__name__}",
            details={"path": str(request.url.path), "method": request.method}
        )
        
        return JSONResponse(
            status_code=500,
            content=internal_error.to_dict()
        )
