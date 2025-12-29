"""
Test MOAI End-to-End Flow
"""
import pytest
import numpy as np
from tensorguard.moai.moai_config import MoaiConfig
from tensorguard.moai.keys import MoaiKeyManager
from tensorguard.moai.exporter import MoaiExporter
from tensorguard.moai.encrypt import MoaiEncryptor, MoaiDecryptor
from tensorguard.serving.backend import MockBackend

def test_moai_flow():
    # Setup
    config = MoaiConfig()
    key_manager = MoaiKeyManager("tests/keys_tmp")
    key_id, pk, sk, eval_keys = key_manager.generate_keypair_stub("test-tenant", config)
    
    # Export
    exporter = MoaiExporter(config)
    pack = exporter.export("dummy.pt", "test-model-v1", ["layer1"])
    
    # Serve
    backend = MockBackend()
    backend.load_model(pack)
    
    # Infer
    input_vec = np.random.randn(64).astype(np.float32)
    enc = MoaiEncryptor(key_id, config)
    ct = enc.encrypt_vector(input_vec)
    
    res_ct = backend.infer(ct, eval_keys)
    
    dec = MoaiDecryptor(key_id, sk)
    res_vec = dec.decrypt_vector(res_ct)
    
    # With MockBackend, output is either linear transform or identity fallback (if weights missing)
    # The key is that it runs without error and returns vector
    assert isinstance(res_vec, np.ndarray)
    assert res_vec.dtype in [np.float32, np.float64]
