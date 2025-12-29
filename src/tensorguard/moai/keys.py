"""
MOAI Key Management System (CKKS)
Distinguishes between Training Keys (N2HE) and Inference Keys (CKKS).
"""

import os
import json
import base64
import secrets
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from .moai_config import MoaiConfig

@dataclass
class CkksKeyMetadata:
    """Metadata for a tenant's FHE evaluation keys."""
    key_id: str
    tenant_id: str
    created_at: str
    poly_modulus_degree: int
    has_relin_keys: bool
    has_galois_keys: bool
    version: str = "1.0.0"

class MoaiKeyManager:
    """
    Manages generation, storage, and loading of CKKS keys.
    Note: Actual key generation logic would call into a C++ backend (SEAL/OpenFHE).
    For now, this manages the lifecycle and metadata.
    """
    
    def __init__(self, key_store_path: str = "keys/moai"):
        self.key_store_path = Path(key_store_path)
        self.key_store_path.mkdir(parents=True, exist_ok=True)
        
    def generate_keypair_stub(self, tenant_id: str, config: MoaiConfig) -> Tuple[str, bytes, bytes, bytes]:
        """
        Generate a mock keypair for testing/development.
        Returns: (key_id, public_key, secret_key, eval_keys)
        """
        key_id = f"moai_{secrets.token_hex(8)}"
        
        # Mock key material (in production, these would be binary blobs from SEAL)
        pk = b"mock_public_key_" + secrets.token_bytes(32)
        sk = b"mock_secret_key_" + secrets.token_bytes(32)
        eval_k = b"mock_eval_keys_" + secrets.token_bytes(128)
        
        # Save metadata
        meta = CkksKeyMetadata(
            key_id=key_id,
            tenant_id=tenant_id,
            created_at=datetime.utcnow().isoformat(),
            poly_modulus_degree=config.poly_modulus_degree,
            has_relin_keys=True,
            has_galois_keys=True
        )
        
        self._save_metadata(key_id, meta)
        return key_id, pk, sk, eval_k

    def _save_metadata(self, key_id: str, meta: CkksKeyMetadata):
        """Save key metadata to disk."""
        meta_path = self.key_store_path / f"{key_id}.meta.json"
        with open(meta_path, 'w') as f:
            json.dump(asdict(meta), f, indent=2)

    def load_metadata(self, key_id: str) -> Optional[CkksKeyMetadata]:
        """Load key metadata."""
        meta_path = self.key_store_path / f"{key_id}.meta.json"
        if not meta_path.exists():
            return None
            
        with open(meta_path, 'r') as f:
            data = json.load(f)
        return CkksKeyMetadata(**data)

    def save_keys(self, key_id: str, pk: bytes, sk: Optional[bytes] = None, eval_k: Optional[bytes] = None):
        """Save binary key artifacts."""
        # Public Key
        with open(self.key_store_path / f"{key_id}.pub", 'wb') as f:
            f.write(pk)
            
        # Secret Key (Client side only usually, but stored here for dev/sim)
        if sk:
            with open(self.key_store_path / f"{key_id}.secret", 'wb') as f:
                f.write(sk)
                
        # Evaluation Keys (Public, sent to server)
        if eval_k:
            with open(self.key_store_path / f"{key_id}.eval", 'wb') as f:
                f.write(eval_k)

    def load_public_context(self, key_id: str) -> Tuple[bytes, bytes]:
        """Load public key and evaluation keys (server context)."""
        pub_path = self.key_store_path / f"{key_id}.pub"
        eval_path = self.key_store_path / f"{key_id}.eval"
        
        if not pub_path.exists() or not eval_path.exists():
            raise FileNotFoundError(f"Keys not found for {key_id}")
            
        return pub_path.read_bytes(), eval_path.read_bytes()
