import importlib.util
import os

from .environment import get_environment, is_production


class StartupValidationError(RuntimeError):
    """Raised when startup configuration fails validation."""


def _check_dependency(module_name: str, description: str) -> None:
    if importlib.util.find_spec(module_name) is None:
        raise StartupValidationError(
            f"Missing dependency: {description}. Install the required package before startup."
        )


def validate_startup_config() -> None:
    """Validate startup configuration and dependencies."""
    if not is_production():
        return

    errors = []

    if not os.getenv("TG_SECRET_KEY"):
        errors.append("TG_SECRET_KEY must be set in production.")

    if not os.getenv("DATABASE_URL"):
        errors.append("DATABASE_URL must be set in production.")

    if os.getenv("TG_DEMO_MODE", "false").lower() == "true":
        errors.append("TG_DEMO_MODE cannot be enabled in production.")

    if os.getenv("TG_ENABLE_AGGREGATION", "false").lower() == "true":
        try:
            _check_dependency("flwr", "Flower aggregation runtime (flwr)")
        except StartupValidationError as exc:
            errors.append(str(exc))

    if os.getenv("TG_ENABLE_PQC", "false").lower() == "true":
        try:
            _check_dependency("oqs", "liboqs-python PQC backend (oqs)")
        except StartupValidationError as exc:
            errors.append(str(exc))

    if errors:
        error_message = "Startup validation failed in production:\n- " + "\n- ".join(errors)
        raise StartupValidationError(error_message)
