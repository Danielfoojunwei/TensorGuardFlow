"""
MOAI End-to-End Demo
Simulates: Training -> Export -> Serving -> Inference
"""

import sys
import os
import numpy as np
import base64
import time

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from tensorguard.moai.moai_config import MoaiConfig
from tensorguard.moai.keys import MoaiKeyManager
from tensorguard.moai.exporter import MoaiExporter
from tensorguard.moai.encrypt import MoaiEncryptor, MoaiDecryptor
from tensorguard.serving.backend import MockBackend

def main():
    print("=== TensorGuard MOAI Flow Demo ===")
    
    # 1. Configuration & Keygen
    print("\n[1] Generating Keys...")
    config = MoaiConfig()
    key_manager = MoaiKeyManager()
    key_id, pk, sk, eval_keys = key_manager.generate_keypair_stub("tenant-A", config)
    print(f"    Key ID: {key_id}")
    
    # 2. Export Model (Mock Training Checkpoint)
    print("\n[2] Exporting ModelPack...")
    exporter = MoaiExporter(config)
    # We mock a model path; exporter will generate random weights
    model_pack = exporter.export("mock_checkpoint.pt", "demo-model-v1", ["policy_head"])
    print(f"    ModelPack ID: {model_pack.meta.model_id}")
    print(f"    Validation Hash: {model_pack.calculate_hash()[:8]}...")
    
    # 3. Load Model in Server (MockBackend)
    print("\n[3] Loading Model into Serving Backend...")
    backend = MockBackend()
    backend.load_model(model_pack)
    print("    Model loaded successfully.")
    
    # 4. Client Encryption
    print("\n[4] Client: Encrypting Input...")
    # Simulate a 64-dim embedding
    input_vector = np.random.randn(64).astype(np.float32)
    encryptor = MoaiEncryptor(key_id, config)
    ciphertext = encryptor.encrypt_vector(input_vector)
    print(f"    Ciphertext Size: {len(ciphertext)} bytes")
    
    # 5. Inference (Server Limit)
    print("\n[5] Server: Running Inference...")
    t0 = time.time()
    result_ciphertext = backend.infer(ciphertext, eval_keys)
    dt = (time.time() - t0) * 1000
    print(f"    Inference Time: {dt:.2f}ms")
    print(f"    Result Size: {len(result_ciphertext)} bytes")
    
    # 6. Client Decryption
    print("\n[6] Client: Decrypting Result...")
    decryptor = MoaiDecryptor(key_id, sk)
    result_vector = decryptor.decrypt_vector(result_ciphertext)
    
    print("\n=== Result Verification ===")
    print(f"Input Shape: {input_vector.shape}")
    print(f"Output Shape: {result_vector.shape}")
    print("First 5 values:", result_vector[:5])
    print("\n[+] Demo Complete!")

if __name__ == "__main__":
    main()
