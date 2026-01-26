"""
Demo Mode Utilities

Provides centralized TG_DEMO_MODE gating for simulation and fixture code.

SECURITY:
- Demo mode is disabled by default
- Demo mode is BLOCKED in production (TG_ENVIRONMENT=production)
- All demo code paths must be explicitly gated

Usage:
    from tensorguard.utils.demo_mode import is_demo_mode, require_demo_mode, demo_only

    # Check if demo mode is enabled
    if is_demo_mode():
        use_demo_fixtures()

    # Decorator to mark functions as demo-only
    @demo_only
    def load_demo_data():
        ...

    # Explicit requirement (raises error if not in demo mode)
    require_demo_mode("This feature")
"""

import functools
import logging
import os
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])

# Configuration
_TG_DEMO_MODE = os.getenv("TG_DEMO_MODE", "false").lower() == "true"
_TG_ENVIRONMENT = os.getenv("TG_ENVIRONMENT", "development")


class DemoModeError(RuntimeError):
    """Raised when demo mode is required but not available."""

    def __init__(self, feature: str = "This feature"):
        super().__init__(
            f"{feature} requires TG_DEMO_MODE=true. "
            f"Current: TG_DEMO_MODE={os.getenv('TG_DEMO_MODE', 'false')}, "
            f"TG_ENVIRONMENT={_TG_ENVIRONMENT}"
        )


class DemoModeBlockedError(RuntimeError):
    """Raised when demo mode is attempted in production."""

    def __init__(self):
        super().__init__(
            "SECURITY VIOLATION: TG_DEMO_MODE=true is not allowed when "
            "TG_ENVIRONMENT=production. Either disable demo mode or "
            "change TG_ENVIRONMENT to 'development' or 'staging'."
        )


def is_demo_mode() -> bool:
    """
    Check if demo mode is enabled.

    Returns:
        True if TG_DEMO_MODE=true AND not in production, False otherwise

    Note:
        Demo mode is ALWAYS disabled in production, regardless of env var
    """
    if _TG_ENVIRONMENT == "production":
        if _TG_DEMO_MODE:
            logger.critical(
                "SECURITY: TG_DEMO_MODE=true ignored in production environment"
            )
        return False
    return _TG_DEMO_MODE


def is_demo_mode_requested() -> bool:
    """
    Check if demo mode was explicitly requested (even if blocked).

    Use this for logging/diagnostics only.
    """
    return _TG_DEMO_MODE


def require_demo_mode(feature: str = "This feature") -> None:
    """
    Assert that demo mode is enabled.

    Args:
        feature: Description of the feature requiring demo mode

    Raises:
        DemoModeBlockedError: If in production with demo mode requested
        DemoModeError: If demo mode is not enabled
    """
    if _TG_ENVIRONMENT == "production" and _TG_DEMO_MODE:
        raise DemoModeBlockedError()

    if not is_demo_mode():
        raise DemoModeError(feature)


def demo_only(func: F) -> F:
    """
    Decorator to mark a function as demo-only.

    The decorated function will:
    - Raise DemoModeError if called outside demo mode
    - Log a warning when called in demo mode
    - Never execute in production

    Usage:
        @demo_only
        def load_demo_fixtures():
            return [...]

    Args:
        func: Function to decorate

    Returns:
        Wrapped function that checks demo mode
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        require_demo_mode(f"Function '{func.__name__}'")
        logger.warning(
            f"DEMO MODE: Executing demo-only function '{func.__name__}' - "
            "NOT FOR PRODUCTION"
        )
        return func(*args, **kwargs)

    return wrapper  # type: ignore


def demo_fallback(
    fallback_value: Any = None,
    log_level: int = logging.WARNING,
) -> Callable[[F], F]:
    """
    Decorator that provides a fallback value when not in demo mode.

    Use this for functions that should return demo data in demo mode
    but a default value otherwise.

    Usage:
        @demo_fallback(fallback_value=[])
        def get_demo_users():
            return [User(id="demo-1", name="Demo User")]

    Args:
        fallback_value: Value to return when not in demo mode
        log_level: Logging level for demo mode warning

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if is_demo_mode():
                logger.log(
                    log_level,
                    f"DEMO MODE: Using demo data from '{func.__name__}'"
                )
                return func(*args, **kwargs)
            return fallback_value

        return wrapper  # type: ignore

    return decorator


def get_demo_mode_status() -> dict:
    """
    Get comprehensive demo mode status for diagnostics.

    Returns:
        Dict with demo mode configuration details
    """
    return {
        "demo_mode_requested": _TG_DEMO_MODE,
        "demo_mode_effective": is_demo_mode(),
        "environment": _TG_ENVIRONMENT,
        "is_production": _TG_ENVIRONMENT == "production",
        "blocked_reason": (
            "Production environment" if _TG_ENVIRONMENT == "production" and _TG_DEMO_MODE
            else None
        ),
    }
