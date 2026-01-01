import unittest
import os
import shutil
from fastapi.testclient import TestClient
from tensorguard.platform.main import app

class TestPlatformSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_upload_path_traversal_sanitization(self):
        """Test that uploaded filenames with ../ are sanitized."""
        # Create a dummy TGSP file
        filename = "../../../evil_script.py"
        # We need a valid-ish TGSP for the inspector to not fail early
        # Actually the inspector reads it, so let's just create a minimal ZIP
        import zipfile
        import io
        from tensorguard.tgsp import spec
        
        # We need a manifest in the ZIP
        from tensorguard.tgsp.manifest import PackageManifest
        m = PackageManifest()
        m_bytes = m.to_canonical_cbor()
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as z:
            z.writestr(spec.MANIFEST_PATH, m_bytes)
        
        zip_bytes = zip_buffer.getvalue()
        
        response = self.client.post(
            "/api/community/tgsp/upload",
            files={"file": (filename, zip_bytes, "application/octet-stream")}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify the saved filename is just 'evil_script.py'
        self.assertEqual(data["filename"], "evil_script.py")
        
        # Verify it's in the designated storage dir, not root
        storage_path = data["storage_path"]
        self.assertIn("storage", storage_path)
        self.assertNotIn("..", storage_path)

if __name__ == "__main__":
    unittest.main()
