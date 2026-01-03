"""
================================================================================
                         SECURITY WARNING - SIMULATOR ONLY
================================================================================

This module is a FUNCTIONAL SIMULATOR of ML-DSA-65 (Dilithium-3).

IT PROVIDES NO CRYPTOGRAPHIC SECURITY WHATSOEVER.

This implementation exists solely for:
- API compatibility testing
- Performance benchmarking
- Integration development in environments without liboqs

DO NOT USE IN PRODUCTION. For real post-quantum security, use:
- liboqs (Open Quantum Safe): https://openquantumsafe.org/
- PQClean: https://github.com/PQClean/PQClean
- NIST PQC implementations

================================================================================
"""

import os
import hashlib
import warnings
from typing import Tuple
from .agility import PostQuantumSig

# Emit warning on module import
warnings.warn(
    "tensorguard.crypto.pqc.dilithium: Using SIMULATED Dilithium-3. "
    "This provides NO SECURITY. Use liboqs for production.",
    category=UserWarning,
    stacklevel=2
)


class Dilithium3(PostQuantumSig):
    """
    SIMULATOR for ML-DSA-65 (Dilithium-3).

    WARNING: This is NOT a secure implementation. It provides correct signature
    sizes and API contracts for testing purposes only. The "signatures" are
    deterministic hashes with NO security properties.

    For production use, integrate with liboqs or another audited implementation.
    """

    NAME = "ML-DSA-65-SIMULATOR"
    PK_SIZE = 1952
    SK_SIZE = 4032
    SIG_SIZE = 3293

    _WARNED = False

    def __init__(self):
        if not Dilithium3._WARNED:
            warnings.warn(
                "Dilithium3 SIMULATOR instantiated. NO SECURITY PROVIDED.",
                category=UserWarning,
                stacklevel=2
            )
            Dilithium3._WARNED = True

    @property
    def name(self) -> str:
        return self.NAME

    def keygen(self) -> Tuple[bytes, bytes]:
        """Generate simulated keypair. NO SECURITY."""
        sk = os.urandom(self.SK_SIZE)
        pk_seed = hashlib.sha256(sk).digest()
        pk = pk_seed + os.urandom(self.PK_SIZE - 32)
        return pk, sk

    def sign(self, sk: bytes, message: bytes) -> bytes:
        """Generate simulated signature. NO SECURITY - deterministic hash."""
        pk_seed = hashlib.sha256(sk).digest()
        h = hashlib.sha256(pk_seed + message).digest()

        # Deterministic padding to fill SIG_SIZE (INSECURE)
        padding = (h * 103)[:self.SIG_SIZE]
        return padding

    def verify(self, pk: bytes, message: bytes, signature: bytes) -> bool:
        """Verify simulated signature. NO SECURITY."""
        if len(pk) != self.PK_SIZE:
            return False
        if len(signature) != self.SIG_SIZE:
            return False

        pk_seed = pk[:32]
        h = hashlib.sha256(pk_seed + message).digest()
        expected_padding = (h * 103)[:self.SIG_SIZE]

        return signature == expected_padding
