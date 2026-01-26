"""
TensorGuard Platform Middleware

Provides:
- RequestIDMiddleware: Adds unique request ID to all requests
- StructuredLoggingMiddleware: Logs all requests with route, status, latency
- RateLimitMiddleware: Token-bucket rate limiting per IP
- SecretRedactionFilter: Log filter to redact secrets/tokens
- ErrorHandlerMiddleware: Consistent error response format

All middleware respects the request_id for traceability.
"""

import json
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from datetime import datetime
from threading import Lock
from typing import Callable, Dict, Optional, Tuple

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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token-bucket rate limiting middleware.

    Features:
    - Per-IP rate limiting
    - Configurable limits per path pattern
    - Stricter limits for auth endpoints
    - Returns 429 with Retry-After header when exceeded

    Configuration via environment:
    - TG_RATE_LIMIT_GENERAL: requests/second for general endpoints (default: 100)
    - TG_RATE_LIMIT_AUTH: requests/second for auth endpoints (default: 10)
    - TG_RATE_LIMIT_BURST: burst capacity multiplier (default: 3)
    """

    # Path patterns for stricter rate limiting
    AUTH_PATHS = {"/auth/token", "/api/v1/auth/token", "/auth/login", "/api/v1/auth/login"}

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        # Configuration
        self.general_rate = float(os.getenv("TG_RATE_LIMIT_GENERAL", "100"))  # req/sec
        self.auth_rate = float(os.getenv("TG_RATE_LIMIT_AUTH", "10"))  # req/sec
        self.burst_multiplier = float(os.getenv("TG_RATE_LIMIT_BURST", "3"))

        # Token buckets: {ip: (tokens, last_update)}
        self._buckets: Dict[str, Tuple[float, float]] = defaultdict(lambda: (self._get_burst(False), time.time()))
        self._auth_buckets: Dict[str, Tuple[float, float]] = defaultdict(lambda: (self._get_burst(True), time.time()))
        self._lock = Lock()

        # Exempt paths from rate limiting
        self.exempt_paths = {"/health", "/healthz", "/ready", "/readyz", "/live", "/metrics"}

    def _get_burst(self, is_auth: bool) -> float:
        """Get burst capacity for bucket type."""
        rate = self.auth_rate if is_auth else self.general_rate
        return rate * self.burst_multiplier

    def _get_bucket(self, ip: str, is_auth: bool) -> Tuple[float, float]:
        """Get or create token bucket for IP."""
        buckets = self._auth_buckets if is_auth else self._buckets
        return buckets[ip]

    def _update_bucket(self, ip: str, is_auth: bool, tokens: float, timestamp: float):
        """Update token bucket."""
        buckets = self._auth_buckets if is_auth else self._buckets
        buckets[ip] = (tokens, timestamp)

    def _consume_token(self, ip: str, is_auth: bool) -> Tuple[bool, float]:
        """
        Attempt to consume a token from the bucket.

        Returns:
            (allowed, retry_after_seconds)
        """
        with self._lock:
            tokens, last_update = self._get_bucket(ip, is_auth)
            now = time.time()

            # Refill tokens based on time elapsed
            rate = self.auth_rate if is_auth else self.general_rate
            burst = self._get_burst(is_auth)
            elapsed = now - last_update
            tokens = min(burst, tokens + elapsed * rate)

            if tokens >= 1.0:
                # Consume token
                self._update_bucket(ip, is_auth, tokens - 1.0, now)
                return True, 0.0
            else:
                # Calculate retry time
                retry_after = (1.0 - tokens) / rate
                self._update_bucket(ip, is_auth, tokens, now)
                return False, retry_after

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Get client IP (consider X-Forwarded-For in production)
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        # Determine if this is an auth endpoint (stricter limits)
        is_auth = request.url.path in self.AUTH_PATHS

        # Check rate limit
        allowed, retry_after = self._consume_token(client_ip, is_auth)

        if not allowed:
            request_id = getattr(request.state, "request_id", None) or get_request_id() or "-"
            logger.warning(
                f"[{request_id}] Rate limit exceeded for {client_ip} on {request.url.path}",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "path": request.url.path,
                    "retry_after": retry_after,
                }
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please slow down.",
                    },
                    "request_id": request_id,
                },
                headers={"Retry-After": str(int(retry_after + 1))},
            )

        return await call_next(request)


class SecretRedactionFilter(logging.Filter):
    """
    Log filter that redacts sensitive information from log messages.

    Redacts:
    - Bearer tokens
    - Authorization headers
    - API keys
    - Secret keys
    - Passwords
    - JWT tokens
    """

    # Patterns to redact (pattern, replacement)
    REDACTION_PATTERNS = [
        # Bearer tokens
        (re.compile(r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+', re.IGNORECASE), 'Bearer [REDACTED]'),
        (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.IGNORECASE), 'Bearer [REDACTED]'),
        # Authorization header values
        (re.compile(r'Authorization["\']?\s*[:=]\s*["\']?[A-Za-z0-9\-_\.]+["\']?', re.IGNORECASE), 'Authorization: [REDACTED]'),
        # API keys (various formats)
        (re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9\-_]+["\']?', re.IGNORECASE), 'api_key=[REDACTED]'),
        (re.compile(r'x-api-key["\']?\s*[:=]\s*["\']?[A-Za-z0-9\-_]+["\']?', re.IGNORECASE), 'x-api-key: [REDACTED]'),
        # Secret keys
        (re.compile(r'secret[_-]?key["\']?\s*[:=]\s*["\']?[^\s,\}\"\']+["\']?', re.IGNORECASE), 'secret_key=[REDACTED]'),
        (re.compile(r'TG_SECRET_KEY\s*=\s*[^\s]+', re.IGNORECASE), 'TG_SECRET_KEY=[REDACTED]'),
        (re.compile(r'TG_VAULT_MASTER_KEY\s*=\s*[^\s]+', re.IGNORECASE), 'TG_VAULT_MASTER_KEY=[REDACTED]'),
        # Passwords
        (re.compile(r'password["\']?\s*[:=]\s*["\']?[^\s,\}\"\']+["\']?', re.IGNORECASE), 'password=[REDACTED]'),
        # Database URLs with passwords
        (re.compile(r'://[^:]+:([^@]+)@', re.IGNORECASE), '://[user]:[REDACTED]@'),
        # JWT tokens (3 parts separated by dots)
        (re.compile(r'eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'), '[JWT_REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and redact sensitive information from log record."""
        # Redact message
        if record.msg:
            record.msg = self._redact(str(record.msg))

        # Redact args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact(str(a)) if isinstance(a, str) else a for a in record.args)

        return True

    def _redact(self, text: str) -> str:
        """Apply all redaction patterns to text."""
        for pattern, replacement in self.REDACTION_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


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
    - Secret redaction filter to prevent credential leakage
    - Proper log levels
    """
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

    # Add console handler with secret redaction filter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SecretRedactionFilter())  # Redact secrets from all logs
    root_logger.addHandler(console_handler)

    # Set levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
