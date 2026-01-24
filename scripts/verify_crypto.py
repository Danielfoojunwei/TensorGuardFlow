
"""
Verification Script for TensorGuard Crypto Modules (N2HE & MOAI)
"""
import sys
import os
import logging
import numpy as np

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CryptoVerifier")

import time

def test_n2he():
    logger.info("--- Testing N2HE (Core) ---")
    try:
        from tensorguard.core.crypto import N2HEEncryptor, N2HEParams
        
        # 1. Initialize
        start = time.time()
        encryptor = N2HEEncryptor(security_level=128)
        init_time = (time.time() - start) * 1000
        logger.info(f"N2HE Encryptor initialized in {init_time:.2f}ms.")
        
        # 2. Encrypt/Decrypt
        data = b"Hello TensorGuard Homomorphic World!" * 1000 # Larger data for measurement
        start = time.time()
        ciphertext = encryptor.encrypt(data)
        enc_time = (time.time() - start) * 1000
        logger.info(f"Encrypted {len(data)} bytes in {enc_time:.2f}ms.")
        
        start = time.time()
        decrypted = encryptor.decrypt(ciphertext)
        dec_time = (time.time() - start) * 1000
        assert decrypted == data
        logger.info(f"Decrypted in {dec_time:.2f}ms. Successful match.")
        
        return {"init_ms": init_time, "enc_ms": enc_time, "dec_ms": dec_time}
    except Exception as e:
        logger.error(f"N2HE Test failed: {e}")
        return None

def test_moai():
    logger.info("--- Testing MOAI (FHE Inference) ---")
    try:
        import tenseal as ts
        from tensorguard.moai.keys import MoaiKeyManager
        from tensorguard.moai.encrypt import MoaiEncryptor, MoaiDecryptor
        from tensorguard.moai.moai_config import MoaiConfig
        
        # 1. Generate Keys
        km = MoaiKeyManager("tmp_keys")
        config = MoaiConfig()
        tid = "test_tenant"
        
        logger.info("Generating Keypair...")
        start = time.time()
        key_id, pub_ctx, sec_ctx, eval_k = km.generate_keypair(tid, config)
        keygen_time = (time.time() - start) * 1000
        logger.info(f"Keys generated in {keygen_time:.2f}ms.")
        
        # 2. Encrypt
        vec = np.random.rand(1024)
        encryptor = MoaiEncryptor(key_id, sec_ctx)
        start = time.time()
        enc_vec = encryptor.encrypt_vector(vec)
        enc_time = (time.time() - start) * 1000
        logger.info(f"Vector (1024) encrypted in {enc_time:.2f}ms.")
        
        # 3. Decrypt
        decryptor = MoaiDecryptor(key_id, sec_ctx)
        start = time.time()
        dec_vec = decryptor.decrypt_vector(enc_vec)
        dec_time = (time.time() - start) * 1000
        logger.info(f"Decrypted in {dec_time:.2f}ms.")
        
        assert np.allclose(dec_vec, vec, atol=0.01)
        return {"keygen_ms": keygen_time, "enc_ms": enc_time, "dec_ms": dec_time}
    except Exception as e:
        logger.error(f"MOAI Test failed: {e}")
        return None

if __name__ == "__main__":
    n2he_res = test_n2he()
    print("\n")
    moai_res = test_moai()
    
    print("\n" + "="*30)
    print("   CRYPTO METRICS SUMMARY")
    print("="*30)
    if n2he_res:
        print(f"N2HE Init: {n2he_res['init_ms']:.2f} ms")
        print(f"N2HE Enc:  {n2he_res['enc_ms']:.2f} ms")
        print(f"N2HE Dec:  {n2he_res['dec_ms']:.2f} ms")
    if moai_res:
        print(f"MOAI Keygen: {moai_res['keygen_ms']:.2f} ms")
        print(f"MOAI Enc:    {moai_res['enc_ms']:.2f} ms")
        print(f"MOAI Dec:    {moai_res['dec_ms']:.2f} ms")
