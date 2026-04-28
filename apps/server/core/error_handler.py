"""
Unified error handler for API exceptions.

Provides custom APIException class and global exception handling.
"""
import logging
import traceback
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.error_codes import ErrorCode
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


class APIException(HTTPException):
    """
    Custom API exception with error code support.

    Usage:
        raise APIException(
            error_code=ErrorCode.PROJECT_NOT_FOUND,
            status_code=404
        )

    The response will include:
    {
        "detail": "ERR_PROJECT_NOT_FOUND",
        "error_code": "ERR_PROJECT_NOT_FOUND"
    }
    """

    def __init__(
        self,
        error_code: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        headers: dict[str, Any] | None = None,
        detail: Any | None = None,
        message: str | None = None,
        **kwargs,
    ):
        self.error_code = error_code
        # Backward compatibility: many callsites still pass `message=...`.
        if detail is None and message is not None:
            detail = message
        # If detail is provided, use it; otherwise use error_code
        detail_value = detail if detail is not None else error_code
        # Ignore unknown kwargs to prevent runtime crashes from legacy callsites.
        super().__init__(status_code=status_code, detail=detail_value, headers=headers)


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    Handle APIException instances.

    Returns standardized error response with error code.
    """
    log_with_context(
        logger,
        logging.WARNING,
        "APIException raised",
        error_code=exc.error_code,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.error_code,
            "error_code": exc.error_code,
            "error_detail": exc.detail,
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle standard HTTPException instances.

    This is for backward compatibility with existing code that still uses
    standard HTTPException.
    """
    log_with_context(
        logger,
        logging.WARNING,
        "HTTPException raised",
        detail=str(exc.detail),
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle request validation errors.

    Returns detailed validation error information.
    """
    log_with_context(
        logger,
        logging.WARNING,
        "Request validation failed",
        errors=str(exc.errors()),
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": ErrorCode.VALIDATION_ERROR,
            "error_code": ErrorCode.VALIDATION_ERROR,
            "errors": exc.errors(),
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all unhandled exceptions.

    This is a catch-all handler for unexpected errors.
    """
    log_with_context(
        logger,
        logging.ERROR,
        "Unhandled exception",
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback=traceback.format_exc(),
        path=request.url.path,
        method=request.method,
    )

    # Don't expose internal errors to clients in production
    error_detail = ErrorCode.INTERNAL_SERVER_ERROR

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_detail, "error_code": error_detail},
    )
