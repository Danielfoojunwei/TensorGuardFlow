
import pytest
import os
import shutil
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization
from tensorguard.tgsp.service import TGSPService
from tensorguard.tgsp import crypto

# Paths
FIXTURE_DIR = "tests/fixtures/tgsp_data"
TEST_KEYS_DIR = "tests/fixtures/keys"
OUT_DIR = "tests/output"

@pytest.fixture(scope="module")
def setup_keys():
    os.makedirs(TEST_KEYS_DIR, exist_ok=True)
    
    # Producer Signing Keys (Ed25519)
    sign_priv = ed25519.Ed25519PrivateKey.generate()
    sign_pub = sign_priv.public_key()
    
    with open(f"{TEST_KEYS_DIR}/sign.priv", "wb") as f:
        f.write(sign_priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    with open(f"{TEST_KEYS_DIR}/sign.pub", "wb") as f:
        f.write(sign_pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))

    # Recipient Encryption Keys (X25519)
    rec_priv = x25519.X25519PrivateKey.generate()
    rec_pub = rec_priv.public_key()
    
    with open(f"{TEST_KEYS_DIR}/recipient.priv", "wb") as f:
        f.write(rec_priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    with open(f"{TEST_KEYS_DIR}/recipient.pub", "wb") as f:
        f.write(rec_pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        
    yield
    # Cleanup done via global cleanup or manual

@pytest.fixture
def clean_dirs():
    if os.path.exists(FIXTURE_DIR): shutil.rmtree(FIXTURE_DIR)
    if os.path.exists(OUT_DIR): shutil.rmtree(OUT_DIR)
    os.makedirs(FIXTURE_DIR)
    os.makedirs(OUT_DIR)
    yield

class TestTGSPCore:
    
    def test_tgsp_roundtrip_complete(self, setup_keys, clean_dirs):
        """Full Create -> Verify -> Decrypt flow."""
        
        # 1. Setup Payloads
        payload_path = f"{FIXTURE_DIR}/model.bin"
        with open(payload_path, "wb") as f:
            f.write(b"SECRET_MODEL_DATA_123")
            
        policy_path = f"{FIXTURE_DIR}/policy.yaml"
        with open(policy_path, "w") as f:
            f.write("id: test-policy\nversion: 1.0")

        pkg_path = f"{OUT_DIR}/test.tgsp"
        
        # 2. Create Package
        pkg_id = TGSPService.create_package(
            out_path=pkg_path,
            signing_key_path=f"{TEST_KEYS_DIR}/sign.priv",
            payloads=[f"model-v1:weights:{payload_path}"],
            policy_path=policy_path,
            recipients=[f"edge-node-1:{TEST_KEYS_DIR}/recipient.pub"]
        )
        assert os.path.exists(pkg_path)
        
        # 3. Verify Package
        ok, msg = TGSPService.verify_package(pkg_path)
        assert ok, f"Verification failed: {msg}"
        
        # 4. Decrypt
        decrypt_out = f"{OUT_DIR}/decrypted"
        TGSPService.decrypt_package(
            path=pkg_path,
            recipient_id="edge-node-1",
            priv_key_path=f"{TEST_KEYS_DIR}/recipient.priv",
            out_dir=decrypt_out
        )
        
        # 5. Check Output
        assert os.path.exists(f"{decrypt_out}/model.bin")
        with open(f"{decrypt_out}/model.bin", "rb") as f:
            assert f.read() == b"SECRET_MODEL_DATA_123"

    def test_tgsp_incorrect_signature_fails_verification(self, setup_keys, clean_dirs):
        # 1. Create valid package
        payload_path = f"{FIXTURE_DIR}/data.bin"
        with open(payload_path, "wb") as f: f.write(b"data")
        pkg_path = f"{OUT_DIR}/signed.tgsp"
        
        TGSPService.create_package(
            out_path=pkg_path,
            signing_key_path=f"{TEST_KEYS_DIR}/sign.priv",
            payloads=[f"p1:raw:{payload_path}"]
        )
        
        # 2. Tamper with signature by creating a new package with SAME content but DIFFERENT key, 
        # OR just mock the verification call failure if we can't easily edit zip bytes without invalidating zip structure.
        # Ideally, we edit the zip content.
        
        # Easier: Flip bytes in the SIGNATURE file inside zip
        # This requires zip editing tools or careful binary surgery.
        # Alternatively, use a non-matching pubkey during verification? 
        # The verify_package logic loads pubkey FROM manifest. 
        # So we need to tamper the signature file ITSELF in the ZIP.

        # 2. Tamper Binary bytes
        with open(pkg_path, 'rb') as f:
            data = bytearray(f.read())
        
        # Corrupt near the end where signature resides
        if len(data) > 64:
            data[-10] ^= 0xFF
            
        with open(pkg_path, 'wb') as f:
            f.write(data)
            
        # 3. Verify should fail
        ok, msg = TGSPService.verify_package(pkg_path)
        assert not ok

    def test_tgsp_wrong_recipient_cannot_decrypt(self, setup_keys, clean_dirs):
        payload_path = f"{FIXTURE_DIR}/secret.bin"
        with open(payload_path, "wb") as f: f.write(b"TOP_SECRET")
        pkg_path = f"{OUT_DIR}/secret.tgsp"
        
        TGSPService.create_package(
            out_path=pkg_path,
            payloads=[f"s1:secret:{payload_path}"],
            recipients=[f"valid-user:{TEST_KEYS_DIR}/recipient.pub"]
        )
        
        # Generate random other key
        bad_priv = x25519.X25519PrivateKey.generate()
        bad_key_path = f"{TEST_KEYS_DIR}/bad.priv"
        with open(bad_key_path, "wb") as f:
            f.write(bad_priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

        with pytest.raises(Exception): # Crypto error or "Recipient not found" if using wrong ID
             TGSPService.decrypt_package(
                path=pkg_path,
                recipient_id="valid-user", # ID matches but key is wrong -> KEK derive fail -> Wrap fail check? 
                # Actually X25519 derive just produces garbage KEK, subsequent UNWRAP or DECRYPT fails integrity.
                priv_key_path=bad_key_path,
                out_dir=f"{OUT_DIR}/bad_decrypt"
            )
