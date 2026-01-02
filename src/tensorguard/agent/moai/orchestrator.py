"""
MOAI Orchestrator

Manages the lifecycle of FHE-protected models on the Edge Agent.
Responsible for:
1. Securely fetching TGSP packages.
2. Decrypting packages in-memory (SecureMemoryLoader).
3. Loading ModelPacks into the Inference Backend.
"""

import logging
import io
import tarfile
import pickle
import numpy as np
from typing import Optional, Dict

from ...tgsp.payload_crypto import PayloadDecryptor
from ...serving.backend import TenSEALBackend
from ...moai.modelpack import ModelPack
from ...tgsp.format import read_tgsp_header
import tempfile
import os
import io

logger = logging.getLogger(__name__)

class SecureMemoryLoader:
    """
    Decrypts TGSP payloads directly into memory buffers.
    Ensures sensitive model weights never touch the disk.
    """
    
    @staticmethod
    def load_from_stream(encrypted_stream: io.BytesIO, dek: bytes) -> ModelPack:
        """
        Decrypt stream and return ModelPack.
        """
        # 1. Decrypt (Simulated streaming decryption)
        # In a real implementation, we would pipe chunk-by-chunk through PayloadDecryptor
        # directly into the tarfile reader.
        # For this implementation, we decrypt to a BytesIO buffer first.
        
        # We assume the stream contains the raw payload bytes
        encrypted_bytes = encrypted_stream.getvalue()
        
        # We need a decryptor instance. 
        # Note: In real flow, we'd need the nonce and params from the container header.
        # Here we simplify and assume we can pass the decryptor or just do a mock decrypt
        # if the stream is already the "payload" part.
        
        # Mocking the untar process from in-memory bytes
        # Assuming the decrypted payload is a TAR containing 'model_pack.pkl'
        
        try:
            with tarfile.open(fileobj=io.BytesIO(encrypted_bytes), mode="r:*") as tar:
                member_name = "model_pack.pkl"
                try:
                    f = tar.extractfile(member_name)
                    if f:
                        return pickle.load(f)
                except KeyError:
                    logger.error("model_pack.pkl not found in payload")
                    raise
        except Exception as e:
            # Fallback for dev/testing if not a TAR
            logger.debug(f"Failed to untar (likely raw pickle): {e}")
            try:
                return pickle.loads(encrypted_bytes)
            except:
                raise ValueError("Could not load ModelPack from memory")


class MoaiOrchestrator:
    """
    Orchestrates the MOAI inference service agent-side.
    """
    
    def __init__(self):
        self.backend = TenSEALBackend()
        self.active_model_id: Optional[str] = None
        self.is_ready = False
        
    def load_secure_package(self, package_bytes: bytes, dek: bytes):
        """
        Load a TGSP package into the runtime.
        
        Args:
            package_bytes: The FULL TGSP container bytes.
            dek: The Data Encryption Key unwrapped for this device.
        """
        logger.info("Loading secure package into MOAI runtime...")
        
        # Security: Write ENCRYPTED container to temp file for parsing.
        # Plaintext is NEVER written to disk.
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(package_bytes)
            tf_path = tf.name
            
        try:
            # 1. Parse Header
            data = read_tgsp_header(tf_path)
            h = data["header"]
            
            # 2. Setup Decryptor
            nonce_base = bytes.fromhex(h["crypto"]["nonce_base"])
            m_hash = h["hashes"]["manifest"]
            r_hash = h["hashes"]["recipients"]
            
            decryptor = PayloadDecryptor(dek, nonce_base, m_hash, r_hash)
            
            # 3. Stream Decrypt into Memory
            # We decrypt the payload stream into a BytesIO buffer
            decrypted_buffer = io.BytesIO()
            
            with open(tf_path, "rb") as f:
                f.seek(data["payload_offset"])
                total_read = 0
                while total_read < data["payload_len"]:
                    chunk = decryptor.decrypt_chunk_from_stream(f)
                    if not chunk: break
                    decrypted_buffer.write(chunk)
                    # Overhead: 4 len + chunk + 16 tag
                    total_read += (4 + len(chunk) + 16)
                    
            decrypted_buffer.seek(0)
            
            # 4. Load ModelPack
            model_pack = SecureMemoryLoader.load_from_stream(decrypted_buffer, dek)
            
            # 5. Load Backend
            self.backend.load_model(model_pack)
            self.active_model_id = model_pack.meta.model_id
            self.is_ready = True
            
            logger.info(f"MOAI Runtime Ready. Active Model: {self.active_model_id}")
            
        except Exception as e:
            logger.error(f"Failed to load secure package: {e}")
            self.is_ready = False
            raise
        finally:
            # Secure cleanup of encrypted container
            if os.path.exists(tf_path):
                os.unlink(tf_path)

    def infer(self, ciphertext: bytes, eval_keys: bytes) -> bytes:
        """Proxy inference request to backend."""
        if not self.is_ready:
            raise RuntimeError("MoaiOrchestrator not ready (no model loaded)")
            
        return self.backend.infer(ciphertext, eval_keys)
