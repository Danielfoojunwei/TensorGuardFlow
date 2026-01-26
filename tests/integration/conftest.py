"""
Shared fixtures for integration tests.

Handles SQLModel's global metadata issue by using file-based SQLite with proper isolation.
"""

import os
import tempfile

# Ensure development environment BEFORE any imports that might load config
os.environ.setdefault("TG_ENVIRONMENT", "development")

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session", autouse=True)
def import_all_models():
    """
    Import all models once at session start to register them with SQLModel metadata.
    This ensures consistent metadata state across all tests.
    """
    from tensorguard.platform.models import core, identity_models, enablement_models, evidence_models
    from tensorguard.platform.models import telemetry_models
    yield


@pytest.fixture(scope="session")
def test_db_engine():
    """
    Create a single SQLite database for all tests in the session.
    Using session scope avoids repeated metadata/index collision issues.
    """
    # Create a temp file for the database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db_url = f"sqlite:///{db_path}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    # Create all tables once at session start
    SQLModel.metadata.create_all(engine)

    yield engine

    # Cleanup
    engine.dispose()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def session(test_db_engine):
    """Create a database session for tests."""
    with Session(test_db_engine) as session:
        yield session


@pytest.fixture(scope="function")
def client(test_db_engine):
    """Create a test client with database override."""
    from fastapi.testclient import TestClient
    from tensorguard.platform.main import app
    from tensorguard.platform.database import get_session

    def get_session_override():
        with Session(test_db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()
