import unittest
import os
import shutil
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from tensorguard.tgsp import manifest, crypto, cli, spec

class TestTGSP(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tmp_tgsp_test"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Keys
        self.signing_key = ed25519.Ed25519PrivateKey.generate()
        self.signing_key_path = os.path.join(self.test_dir, "producer.priv")
        with open(self.signing_key_path, 'wb') as f:
            f.write(self.signing_key.private_bytes_raw())
            
        self.recipient_key = x25519.X25519PrivateKey.generate()
        self.recipient_priv_path = os.path.join(self.test_dir, "recipient.priv")
        self.recipient_pub_path = os.path.join(self.test_dir, "recipient.pub")
        with open(self.recipient_priv_path, 'wb') as f:
            f.write(self.recipient_key.private_bytes_raw())
        with open(self.recipient_pub_path, 'wb') as f:
            f.write(self.recipient_key.public_key().public_bytes_raw())
            
        # Dummy assets
        self.adapter_path = os.path.join(self.test_dir, "adapter.bin")
        with open(self.adapter_path, 'wb') as f:
            f.write(b"EXTREMELY_SECRET_ADAPTER_WEIGHTS")
            
        self.policy_path = os.path.join(self.test_dir, "policy.yaml")
        with open(self.policy_path, 'w') as f:
            f.write("id: test-policy\nversion: 1.0.0")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_end_to_end_flow(self):
        tgsp_file = os.path.join(self.test_dir, "test.tgsp")
        
        # 1. Create
        class Args:
            out = tgsp_file
            producer_signing_key = self.signing_key_path
            compat_base_model_id = ["llama-3-8b"]
            payload = ["adapter1:weights:" + self.adapter_path]
            policy = self.policy_path
            recipient = ["user1:" + self.recipient_pub_path]
            evidence_report = None
            evidence_html = None
            
        cli.create_tgsp(Args())
        self.assertTrue(os.path.exists(tgsp_file))
        
        # 2. Verify
        class VerifyArgs:
            in_file = tgsp_file
        self.assertTrue(cli.verify_tgsp(VerifyArgs()))
        
        # 3. Decrypt
        out_dir = os.path.join(self.test_dir, "out")
        class DecryptArgs:
            in_file = tgsp_file
            recipient_id = "user1"
            recipient_private_key = self.recipient_priv_path
            outdir = out_dir
            
        cli.decrypt_tgsp(DecryptArgs())
        
        recovered_path = os.path.join(out_dir, "adapter.bin")
        self.assertTrue(os.path.exists(recovered_path))
        with open(recovered_path, 'rb') as f:
            self.assertEqual(f.read(), b"EXTREMELY_SECRET_ADAPTER_WEIGHTS")

    def test_tamper_detection(self):
        tgsp_file = os.path.join(self.test_dir, "tamper.tgsp")
        
        class Args:
            out = tgsp_file
            producer_signing_key = self.signing_key_path
            compat_base_model_id = ["llama-3-8b"]
            payload = ["adapter1:weights:" + self.adapter_path]
            policy = self.policy_path
            recipient = ["user1:" + self.recipient_pub_path]
            evidence_report = None
            evidence_html = None
        
        cli.create_tgsp(Args())
        
        # Tamper ZIP
        import zipfile
        temp_zip = os.path.join(self.test_dir, "temp.zip")
        with zipfile.ZipFile(tgsp_file, 'r') as zin:
            with zipfile.ZipFile(temp_zip, 'w') as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename == "PAYLOAD/adapter1.enc":
                        # Flip a bit
                        data = bytearray(data)
                        data[20] ^= 0xFF
                        data = bytes(data)
                    zout.writestr(item, data)
        
        os.remove(tgsp_file)
        os.rename(temp_zip, tgsp_file)
        
        class VerifyArgs:
            in_file = tgsp_file
        # Verification should fail due to hash mismatch or AEAD tag error (if we decrypted, but here verify checks hash)
        self.assertFalse(cli.verify_tgsp(VerifyArgs()))

if __name__ == "__main__":
    unittest.main()
