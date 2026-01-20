"""
TensorGuard Platform Middleware

Provides:
- RequestIDMiddleware: Adds unique request ID to all requests
- StructuredLoggingMiddleware: Logs all requests with route, status, latency
- ErrorHandlerMiddleware: Consistent error response format

All middleware respects the request_id for traceability.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# Context variable to store request_id across async contexts
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

logger = logging.getLogger("tensorguard.platform")


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to every request.

    The request ID is:
    - Generated if not provided in X-Request-ID header
    - Stored in context for use by other components
    - Added to response headers as X-Request-ID
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())[:8]  # Short UUID for readability

        # Store in context
        token = request_id_var.set(request_id)

        # Attach to request state for endpoint access
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request/response logging.

    Logs:
    - Request: method, path, client IP
    - Response: status code, latency
    - Always includes request_id for correlation
    """

    # Paths to skip logging (high-frequency, low-value)
    SKIP_PATHS = {"/health", "/ready", "/live", "/metrics", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip noisy endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = getattr(request.state, "request_id", None) or get_request_id() or "-"
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # Log request start
        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception as exc:
            # Log exception
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[{request_id}] {method} {path} -> ERROR ({latency_ms:.1f}ms)",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "client_ip": client_ip,
                    "error": str(exc),
                    "latency_ms": latency_ms,
                }
            )
            raise

        # Log response
        latency_ms = (time.time() - start_time) * 1000
        status = response.status_code

        # Use appropriate log level based on status
        if status >= 500:
            log_fn = logger.error
        elif status >= 400:
            log_fn = logger.warning
        else:
            log_fn = logger.info

        log_fn(
            f"[{request_id}] {method} {path} -> {status} ({latency_ms:.1f}ms)",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "client_ip": client_ip,
                "status_code": status,
                "latency_ms": latency_ms,
            }
        )

        return response


class StandardErrorResponse:
    """
    Standard error response format for consistency.

    Format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": {...}  # Optional
        },
        "request_id": "abc123"
    }
    """

    @staticmethod
    def create(
        code: str,
        message: str,
        status_code: int = 500,
        details: Optional[dict] = None,
        request_id: Optional[str] = None,
    ) -> JSONResponse:
        """Create a standardized error response."""
        error_body = {
            "error": {
                "code": code,
                "message": message,
            },
            "request_id": request_id or get_request_id() or "unknown",
        }
        if details:
            error_body["error"]["details"] = details

        return JSONResponse(
            status_code=status_code,
            content=error_body,
        )


# Common error codes
class ErrorCodes:
    # Authentication
    AUTH_REQUIRED = "AUTH_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # Authorization
    FORBIDDEN = "FORBIDDEN"
    INSUFFICIENT_ROLE = "INSUFFICIENT_ROLE"
    ORG_ACCESS_DENIED = "ORG_ACCESS_DENIED"

    # Resource errors
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"

    # Rate limiting
    RATE_LIMITED = "RATE_LIMITED"

    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def setup_logging(log_level: str = "INFO"):
    """
    Configure structured logging for the platform.

    Sets up:
    - JSON-formatted logs for production
    - Human-readable logs for development
    - Proper log levels
    """
    import os

    env = os.getenv("TG_ENVIRONMENT", "development")

    # Create formatter based on environment
    if env == "production":
        # JSON format for production (easier to parse in log aggregators)
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # Human-readable for development
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
