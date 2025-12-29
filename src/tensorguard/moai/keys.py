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
        
    def generate_keypair(self, tenant_id: str, config: MoaiConfig) -> Tuple[str, bytes, bytes, bytes]:
        """
        Generate a REAL TenSEAL CKKS context and keys.
        Returns: (key_id, public_context_bytes, secret_context_bytes, eval_keys_dummy)
        
        Note: TenSEAL bundles keys into the 'context' object.
        - secret_context_bytes: Contains SK (Client only)
        - public_context_bytes: Contains PK + Relin + Galois (Server)
        """
        import tenseal as ts
        key_id = f"moai_{secrets.token_hex(8)}"
        
        # 1. Create TenSEAL Context
        ctx = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=config.poly_modulus_degree,
            coeff_mod_bit_sizes=config.coeff_modulus_bit_sizes
        )
        ctx.global_scale = config.scale
        ctx.generate_galois_keys()
        ctx.generate_relin_keys()
        
        # 2. Serialize
        # Client Secret (Keep this safe!)
        secret_ctx = ctx.serialize(save_public_key=True, save_secret_key=True, save_galois_keys=True, save_relin_keys=True)
        
        # Server Public (No SK)
        public_ctx = ctx.serialize(save_public_key=True, save_secret_key=False, save_galois_keys=True, save_relin_keys=True)
        
        # In TenSEAL, eval keys are part of the context, so we return empty bytes for explicit eval_k arg
        # to match signature, but the public_ctx acts as the eval_keys carrier.
        eval_k = b"" 
        
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
        return key_id, public_ctx, secret_ctx, eval_k

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
