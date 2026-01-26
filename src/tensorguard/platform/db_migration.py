"""
Database migration utilities.

Provides:
- Migration status checking
- Automatic migration on startup (production mode)
- Migration enforcement and validation
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

# Configuration
TG_ENVIRONMENT = os.getenv("TG_ENVIRONMENT", "development")
TG_AUTO_MIGRATE = os.getenv("TG_AUTO_MIGRATE", "false").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tg_platform.db")


def _get_alembic_config() -> Config:
    """Get Alembic configuration pointing to project root."""
    # Find project root (where alembic.ini lives)
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "alembic.ini").exists():
            config_path = parent / "alembic.ini"
            break
    else:
        raise FileNotFoundError("Could not find alembic.ini in project hierarchy")

    config = Config(str(config_path))
    config.set_main_option("script_location", str(parent / "alembic"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    return config


def get_current_revision() -> Optional[str]:
    """Get the current database revision."""
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            return context.get_current_revision()
    except Exception as e:
        logger.error(f"Failed to get current revision: {e}")
        return None
    finally:
        engine.dispose()


def get_head_revision() -> Optional[str]:
    """Get the latest available migration revision."""
    try:
        config = _get_alembic_config()
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        return head
    except Exception as e:
        logger.error(f"Failed to get head revision: {e}")
        return None


def get_pending_migrations() -> List[str]:
    """Get list of pending migration revisions."""
    try:
        config = _get_alembic_config()
        script = ScriptDirectory.from_config(config)
        current = get_current_revision()

        if current is None:
            # No migrations applied yet, return all
            revisions = [rev.revision for rev in script.walk_revisions()]
            return list(reversed(revisions))

        # Get revisions between current and head
        pending = []
        for rev in script.walk_revisions(base=current, inclusive=False):
            pending.append(rev.revision)

        return list(reversed(pending))
    except Exception as e:
        logger.error(f"Failed to get pending migrations: {e}")
        return []


def check_migrations() -> Dict[str, Any]:
    """
    Check migration status.

    Returns:
        Dict with migration status information
    """
    current = get_current_revision()
    head = get_head_revision()
    pending = get_pending_migrations()

    is_current = current == head
    status = {
        "current_revision": current,
        "head_revision": head,
        "is_current": is_current,
        "pending_count": len(pending),
        "pending_revisions": pending,
    }

    if is_current:
        logger.info(f"Database schema is up to date (revision: {current})")
    else:
        logger.warning(
            f"Database schema is behind: {len(pending)} pending migrations. "
            f"Current: {current}, Head: {head}"
        )

    return status


def run_migrations(dry_run: bool = False) -> Tuple[bool, str]:
    """
    Run pending database migrations.

    Args:
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (success, message)
    """
    try:
        status = check_migrations()
        if status["is_current"]:
            return True, "Database is already up to date"

        if dry_run:
            return True, f"Would apply {status['pending_count']} migrations: {status['pending_revisions']}"

        logger.info(f"Running {status['pending_count']} pending migrations...")
        config = _get_alembic_config()
        command.upgrade(config, "head")

        # Verify
        new_status = check_migrations()
        if new_status["is_current"]:
            return True, f"Successfully applied migrations. Now at revision: {new_status['current_revision']}"
        else:
            return False, f"Migrations incomplete. Still pending: {new_status['pending_revisions']}"

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False, f"Migration failed: {e}"


def enforce_migrations() -> None:
    """
    Enforce that database migrations are current.

    In production with TG_AUTO_MIGRATE=true, runs migrations automatically.
    Otherwise, raises an error if migrations are pending.

    Raises:
        RuntimeError: If migrations are pending and auto-migrate is disabled
    """
    status = check_migrations()

    if status["is_current"]:
        return

    if TG_AUTO_MIGRATE:
        logger.info("TG_AUTO_MIGRATE=true, running pending migrations...")
        success, message = run_migrations()
        if not success:
            raise RuntimeError(f"Auto-migration failed: {message}")
        logger.info(message)
        return

    if TG_ENVIRONMENT == "production":
        raise RuntimeError(
            f"Database schema is behind ({status['pending_count']} pending migrations). "
            "Either run 'alembic upgrade head' or set TG_AUTO_MIGRATE=true. "
            f"Pending: {status['pending_revisions']}"
        )
    else:
        logger.warning(
            f"Database has {status['pending_count']} pending migrations. "
            "Run 'alembic upgrade head' to apply. "
            "This would fail in production."
        )


def create_migration(message: str) -> Tuple[bool, str]:
    """
    Create a new migration script.

    Args:
        message: Migration description

    Returns:
        Tuple of (success, message/path)
    """
    try:
        config = _get_alembic_config()
        script = command.revision(config, message=message, autogenerate=True)
        return True, f"Created migration: {script}"
    except Exception as e:
        return False, f"Failed to create migration: {e}"
