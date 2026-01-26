"""
MOAI Encryption/Decryption (TenSEAL)
For client-side preprocessing and postprocessing.

Requires: pip install tensorguard[fl] (includes tenseal)
"""

import numpy as np
from typing import List, Union, TYPE_CHECKING

from .moai_config import MoaiConfig

# Lazy import of tenseal - only required when classes are actually used
_ts = None


def _get_tenseal():
    """Lazy-load tenseal with helpful error message."""
    global _ts
    if _ts is None:
        try:
            import tenseal as ts
            _ts = ts
        except ImportError as e:
            raise ImportError(
                "TenSEAL is required for MOAI encryption/decryption. "
                "Install with: pip install tensorguard[fl]"
            ) from e
    return _ts

class MoaiEncryptor:
    """Client-side encryptor (TenSEAL)."""

    def __init__(self, key_id: str, context_bytes: bytes):
        ts = _get_tenseal()
        self.key_id = key_id
        # Load context from bytes (includes keys)
        self.ctx = ts.context_from(context_bytes)

    def encrypt_vector(self, vector: np.ndarray) -> bytes:
        """
        Encrypt a numpy vector into a REAL CKKS ciphertext.
        """
        ts = _get_tenseal()
        # Ensure it's a 1D vector or flatten it for CKKS packing
        if hasattr(vector, 'flatten'):
            vec_flat = vector.flatten().tolist()
        else:
            vec_flat = list(vector)

        enc_vec = ts.ckks_vector(self.ctx, vec_flat)
        return enc_vec.serialize()


class MoaiDecryptor:
    """Client-side decryptor (TenSEAL)."""

    def __init__(self, key_id: str, context_bytes: bytes):
        ts = _get_tenseal()
        self.key_id = key_id
        self.ctx = ts.context_from(context_bytes)

    def decrypt_vector(self, ciphertext: bytes) -> np.ndarray:
        """
        Decrypt a CKKS ciphertext.
        """
        ts = _get_tenseal()
        try:
            # We need to construct the CKKS vector linked to our context
            enc_vec = ts.ckks_vector_from(self.ctx, ciphertext)

            # Decrypt
            decrypted_list = enc_vec.decrypt()
            return np.array(decrypted_list)

        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
