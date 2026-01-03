"""
================================================================================
                         SECURITY WARNING - SIMULATOR ONLY
================================================================================

This module is a FUNCTIONAL SIMULATOR of ML-KEM-768 (Kyber-768).

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
from .agility import PostQuantumKEM

# Emit warning on module import
warnings.warn(
    "tensorguard.crypto.pqc.kyber: Using SIMULATED Kyber-768. "
    "This provides NO SECURITY. Use liboqs for production.",
    category=UserWarning,
    stacklevel=2
)


class Kyber768(PostQuantumKEM):
    """
    SIMULATOR for ML-KEM-768 (Kyber-768).

    WARNING: This is NOT a secure implementation. It provides correct key and
    ciphertext sizes and API contracts for testing purposes only. The "encryption"
    is trivially reversible XOR masking with NO security properties.

    For production use, integrate with liboqs or another audited implementation.
    """

    NAME = "ML-KEM-768-SIMULATOR"
    PK_SIZE = 1184
    SK_SIZE = 2400
    CT_SIZE = 1088
    SS_SIZE = 32

    _WARNED = False

    def __init__(self):
        if not Kyber768._WARNED:
            warnings.warn(
                "Kyber768 SIMULATOR instantiated. NO SECURITY PROVIDED.",
                category=UserWarning,
                stacklevel=2
            )
            Kyber768._WARNED = True

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def public_key_size(self) -> int:
        return self.PK_SIZE

    @property
    def ciphertext_size(self) -> int:
        return self.CT_SIZE

    def keygen(self) -> Tuple[bytes, bytes]:
        """Generate simulated keypair. NO SECURITY."""
        sk = os.urandom(self.SK_SIZE)
        pk_seed = hashlib.sha256(sk).digest()
        pk = pk_seed + os.urandom(self.PK_SIZE - 32)
        return pk, sk

    def encap(self, pk: bytes) -> Tuple[bytes, bytes]:
        """Simulated encapsulation. NO SECURITY - trivial XOR."""
        if len(pk) != self.PK_SIZE:
            raise ValueError("Invalid Kyber-768 PK size")

        shared_secret = os.urandom(self.SS_SIZE)

        # INSECURE: Simple XOR masking for functional testing only
        key = pk[:32]
        masked_ss = bytes(a ^ b for a, b in zip(shared_secret, key))
        ciphertext = masked_ss + os.urandom(self.CT_SIZE - 32)

        return shared_secret, ciphertext

    def decap(self, sk: bytes, ct: bytes) -> bytes:
        """Simulated decapsulation. NO SECURITY."""
        if len(sk) != self.SK_SIZE:
            raise ValueError("Invalid SK size")
        if len(ct) != self.CT_SIZE:
            raise ValueError("Invalid CT size")

        pk_seed = hashlib.sha256(sk).digest()
        key = pk_seed

        masked_ss = ct[:32]
        shared_secret = bytes(a ^ b for a, b in zip(masked_ss, key))
        return shared_secret
