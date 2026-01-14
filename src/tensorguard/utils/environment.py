import os


def get_environment() -> str:
    """Return the active runtime environment."""
    env = os.getenv("TG_ENVIRONMENT") or os.getenv("TENSORGUARD_ENVIRONMENT")
    if env:
        return env.strip().lower()
    return "development"


def is_production() -> bool:
    """True when running in production mode."""
    return get_environment() == "production"
