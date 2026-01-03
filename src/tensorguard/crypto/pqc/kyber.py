"""
ML-KEM-768 (Kyber-768) Post-Quantum Key Encapsulation Mechanism

This module provides ML-KEM-768 key encapsulation using liboqs (Open Quantum Safe).
ML-KEM-768 is standardized in NIST FIPS 203.

Requirements:
    - liboqs native library: https://github.com/open-quantum-safe/liboqs
    - liboqs-python: pip install liboqs-python

If liboqs is not available, a fallback simulator is used (development only).
"""

import os
import hashlib
import logging
import warnings
from typing import Tuple

from .agility import PostQuantumKEM

logger = logging.getLogger(__name__)

# Try to import liboqs
_LIBOQS_AVAILABLE = False
_oqs = None

try:
    import oqs
    _oqs = oqs
    _LIBOQS_AVAILABLE = True
    logger.info("liboqs loaded successfully - using production PQC")
except ImportError:
    logger.warning(
        "liboqs not available. Install with: pip install liboqs-python "
        "(requires liboqs native library). Falling back to simulator."
    )


class Kyber768(PostQuantumKEM):
    """
    ML-KEM-768 (Kyber-768) Key Encapsulation Mechanism.

    This implementation uses liboqs for production-grade post-quantum security.
    If liboqs is not installed, a functional simulator is used for development.

    Security Level: NIST Level 3 (equivalent to AES-192)
    Standard: NIST FIPS 203 (ML-KEM)

    Example:
        kem = Kyber768()
        pk, sk = kem.keygen()
        shared_secret, ciphertext = kem.encap(pk)
        recovered_secret = kem.decap(sk, ciphertext)
        assert shared_secret == recovered_secret
    """

    NAME = "ML-KEM-768"

    # NIST ML-KEM-768 sizes
    PK_SIZE = 1184
    SK_SIZE = 2400
    CT_SIZE = 1088
    SS_SIZE = 32

    def __init__(self):
        """Initialize Kyber-768 KEM."""
        self._use_liboqs = _LIBOQS_AVAILABLE
        self._kem = None

        if self._use_liboqs:
            try:
                self._kem = _oqs.KeyEncapsulation("ML-KEM-768")
                logger.debug("Kyber768 initialized with liboqs ML-KEM-768")
            except Exception as e:
                logger.warning(f"Failed to initialize liboqs ML-KEM-768: {e}. Using simulator.")
                self._use_liboqs = False

        if not self._use_liboqs:
            warnings.warn(
                "Kyber768: Using SIMULATOR mode - NO CRYPTOGRAPHIC SECURITY. "
                "Install liboqs-python for production use.",
                category=UserWarning,
                stacklevel=2
            )

    @property
    def name(self) -> str:
        if self._use_liboqs:
            return self.NAME
        return f"{self.NAME}-SIMULATOR"

    @property
    def public_key_size(self) -> int:
        return self.PK_SIZE

    @property
    def ciphertext_size(self) -> int:
        return self.CT_SIZE

    @property
    def is_production(self) -> bool:
        """Returns True if using real liboqs implementation."""
        return self._use_liboqs

    def keygen(self) -> Tuple[bytes, bytes]:
        """
        Generate a new ML-KEM-768 keypair.

        Returns:
            Tuple of (public_key, secret_key)
        """
        if self._use_liboqs:
            kem = _oqs.KeyEncapsulation("ML-KEM-768")
            pk = kem.generate_keypair()
            sk = kem.export_secret_key()
            return bytes(pk), bytes(sk)
        else:
            return self._sim_keygen()

    def encap(self, pk: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using the recipient's public key.

        Args:
            pk: Recipient's public key

        Returns:
            Tuple of (shared_secret, ciphertext)
        """
        if len(pk) != self.PK_SIZE:
            raise ValueError(f"Invalid public key size: expected {self.PK_SIZE}, got {len(pk)}")

        if self._use_liboqs:
            kem = _oqs.KeyEncapsulation("ML-KEM-768")
            ciphertext, shared_secret = kem.encap_secret(pk)
            return bytes(shared_secret), bytes(ciphertext)
        else:
            return self._sim_encap(pk)

    def decap(self, sk: bytes, ct: bytes) -> bytes:
        """
        Decapsulate a shared secret using the secret key.

        Args:
            sk: Secret key
            ct: Ciphertext from encapsulation

        Returns:
            Shared secret
        """
        if len(sk) != self.SK_SIZE:
            raise ValueError(f"Invalid secret key size: expected {self.SK_SIZE}, got {len(sk)}")
        if len(ct) != self.CT_SIZE:
            raise ValueError(f"Invalid ciphertext size: expected {self.CT_SIZE}, got {len(ct)}")

        if self._use_liboqs:
            kem = _oqs.KeyEncapsulation("ML-KEM-768", sk)
            shared_secret = kem.decap_secret(ct)
            return bytes(shared_secret)
        else:
            return self._sim_decap(sk, ct)

    # =========================================================================
    # SIMULATOR FALLBACK (for development without liboqs)
    # =========================================================================

    def _sim_keygen(self) -> Tuple[bytes, bytes]:
        """Simulated keygen - NO SECURITY."""
        sk = os.urandom(self.SK_SIZE)
        pk_seed = hashlib.sha256(sk).digest()
        pk = pk_seed + os.urandom(self.PK_SIZE - 32)
        return pk, sk

    def _sim_encap(self, pk: bytes) -> Tuple[bytes, bytes]:
        """Simulated encap - NO SECURITY (trivial XOR)."""
        shared_secret = os.urandom(self.SS_SIZE)
        key = pk[:32]
        masked_ss = bytes(a ^ b for a, b in zip(shared_secret, key))
        ciphertext = masked_ss + os.urandom(self.CT_SIZE - 32)
        return shared_secret, ciphertext

    def _sim_decap(self, sk: bytes, ct: bytes) -> bytes:
        """Simulated decap - NO SECURITY."""
        pk_seed = hashlib.sha256(sk).digest()
        masked_ss = ct[:32]
        shared_secret = bytes(a ^ b for a, b in zip(masked_ss, pk_seed))
        return shared_secret


def is_liboqs_available() -> bool:
    """Check if liboqs is available for production PQC."""
    return _LIBOQS_AVAILABLE
