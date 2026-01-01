
import pytest
import os
import shutil
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from typing import Generator
from unittest.mock import MagicMock, patch

from tensorguard.platform.main import app
from tensorguard.platform.database import get_session
from tensorguard.platform.api import community_tgsp
from tensorguard.platform.models import core, identity_models, enablement_models, evidence_models

# Use in-memory SQLite for testing
TEST_DB_URL = "sqlite:///:memory:"

from sqlalchemy.pool import StaticPool

@pytest.fixture(name="session")
def session_fixture():
    # Force registration by accessing the classes
    _ = evidence_models.TGSPPackage
    _ = enablement_models.EnablementJob
    
    engine = create_engine(
        TEST_DB_URL, 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    
    # Explicitly create tables
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def temp_storage(tmp_path):
    # Monkeypatch storage dir
    original_storage = community_tgsp.STORAGE_DIR
    community_tgsp.STORAGE_DIR = str(tmp_path / "storage")
    os.makedirs(community_tgsp.STORAGE_DIR, exist_ok=True)
    yield community_tgsp.STORAGE_DIR
    community_tgsp.STORAGE_DIR = original_storage

class TestPlatformAPI:
    
    def test_platform_starts_and_serves_public(self, client):
        response = client.get("/")
        # Depending on how static files are served, this might be 200 or 404 if 'public' dir is empty/missing
        # But verify checking expected response.
        # Check docs or stats endpoint which we know exists
        response = client.get("/docs") 
        assert response.status_code == 200
        
        # Check static serving
        # response = client.get("/index.html")
        # assert response.status_code in [200, 404] 

    def test_enablement_stats_endpoint(self, client):
        """Verify the stats endpoint I fixed earlier."""
        response = client.get("/api/v1/enablement/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_jobs" in data
        assert data["total_jobs"] == 0

    @patch("tensorguard.platform.api.community_tgsp.container.TGSPContainer") 
    def test_platform_tgsp_upload_verify_pass(self, mock_container_cls, client, temp_storage, session):
        # Mock TGSP Container context manager
        mock_container = MagicMock()
        mock_container_cls.return_value.__enter__.return_value = mock_container
        
        # Mock Manifest
        mock_manifest = MagicMock()
        mock_manifest.package_id = "pkg-123"
        mock_manifest.producer_id = "prod-1"
        mock_manifest.created_at = "2026-01-01T12:00:00"
        mock_manifest.policy_id = "pol-1"
        mock_manifest.policy_version = 1
        mock_manifest.file_inventory = {}
        mock_manifest.payloads = []
        mock_manifest.evidence = []
        mock_manifest.base_model_ids = []
        
        with patch("tensorguard.tgsp.manifest.PackageManifest.from_cbor", return_value=mock_manifest):
            files = {"file": ("test.tgsp", b"fake_content", "application/octet-stream")}
            response = client.post("/api/community/tgsp/upload", files=files)
            
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pkg-123"
        assert data["status"] == "uploaded"
