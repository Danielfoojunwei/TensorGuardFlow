"""
ML-DSA-65 (Dilithium-3) Post-Quantum Digital Signature Algorithm

This module provides ML-DSA-65 digital signatures using liboqs (Open Quantum Safe).
ML-DSA-65 is standardized in NIST FIPS 204.

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

from .agility import PostQuantumSig

logger = logging.getLogger(__name__)

# Try to import liboqs
_LIBOQS_AVAILABLE = False
_oqs = None

try:
    import oqs
    _oqs = oqs
    _LIBOQS_AVAILABLE = True
    logger.info("liboqs loaded successfully - using production PQC signatures")
except ImportError:
    logger.warning(
        "liboqs not available. Install with: pip install liboqs-python "
        "(requires liboqs native library). Falling back to simulator."
    )


class Dilithium3(PostQuantumSig):
    """
    ML-DSA-65 (Dilithium-3) Digital Signature Algorithm.

    This implementation uses liboqs for production-grade post-quantum security.
    If liboqs is not installed, a functional simulator is used for development.

    Security Level: NIST Level 3 (equivalent to AES-192)
    Standard: NIST FIPS 204 (ML-DSA)

    Example:
        sig = Dilithium3()
        pk, sk = sig.keygen()
        signature = sig.sign(sk, b"message to sign")
        is_valid = sig.verify(pk, b"message to sign", signature)
        assert is_valid
    """

    NAME = "ML-DSA-65"

    # NIST ML-DSA-65 sizes
    PK_SIZE = 1952
    SK_SIZE = 4032
    SIG_SIZE = 3293

    def __init__(self):
        """Initialize Dilithium-3 signature scheme."""
        self._use_liboqs = _LIBOQS_AVAILABLE
        self._sig = None

        if self._use_liboqs:
            try:
                self._sig = _oqs.Signature("ML-DSA-65")
                logger.debug("Dilithium3 initialized with liboqs ML-DSA-65")
            except Exception as e:
                logger.warning(f"Failed to initialize liboqs ML-DSA-65: {e}. Using simulator.")
                self._use_liboqs = False

        if not self._use_liboqs:
            warnings.warn(
                "Dilithium3: Using SIMULATOR mode - NO CRYPTOGRAPHIC SECURITY. "
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
    def secret_key_size(self) -> int:
        return self.SK_SIZE

    @property
    def signature_size(self) -> int:
        return self.SIG_SIZE

    @property
    def is_production(self) -> bool:
        """Returns True if using real liboqs implementation."""
        return self._use_liboqs

    def keygen(self) -> Tuple[bytes, bytes]:
        """
        Generate a new ML-DSA-65 keypair.

        Returns:
            Tuple of (public_key, secret_key)
        """
        if self._use_liboqs:
            sig = _oqs.Signature("ML-DSA-65")
            pk = sig.generate_keypair()
            sk = sig.export_secret_key()
            return bytes(pk), bytes(sk)
        else:
            return self._sim_keygen()

    def sign(self, sk: bytes, message: bytes) -> bytes:
        """
        Sign a message using the secret key.

        Args:
            sk: Secret key
            message: Message to sign

        Returns:
            Signature bytes
        """
        if len(sk) != self.SK_SIZE:
            raise ValueError(f"Invalid secret key size: expected {self.SK_SIZE}, got {len(sk)}")

        if self._use_liboqs:
            sig = _oqs.Signature("ML-DSA-65", sk)
            signature = sig.sign(message)
            return bytes(signature)
        else:
            return self._sim_sign(sk, message)

    def verify(self, pk: bytes, message: bytes, signature: bytes) -> bool:
        """
        Verify a signature using the public key.

        Args:
            pk: Public key
            message: Original message
            signature: Signature to verify

        Returns:
            True if signature is valid, False otherwise
        """
        if len(pk) != self.PK_SIZE:
            return False

        if self._use_liboqs:
            try:
                sig = _oqs.Signature("ML-DSA-65")
                return sig.verify(message, signature, pk)
            except Exception as e:
                logger.debug(f"Signature verification failed: {e}")
                return False
        else:
            return self._sim_verify(pk, message, signature)

    # =========================================================================
    # SIMULATOR FALLBACK (for development without liboqs)
    # =========================================================================

    def _sim_keygen(self) -> Tuple[bytes, bytes]:
        """Simulated keygen - NO SECURITY."""
        sk = os.urandom(self.SK_SIZE)
        pk_seed = hashlib.sha256(sk).digest()
        pk = pk_seed + os.urandom(self.PK_SIZE - 32)
        return pk, sk

    def _sim_sign(self, sk: bytes, message: bytes) -> bytes:
        """Simulated sign - NO SECURITY (deterministic hash)."""
        pk_seed = hashlib.sha256(sk).digest()
        h = hashlib.sha256(pk_seed + message).digest()
        # Deterministic padding to fill SIG_SIZE (INSECURE)
        padding = (h * 103)[:self.SIG_SIZE]
        return padding

    def _sim_verify(self, pk: bytes, message: bytes, signature: bytes) -> bool:
        """Simulated verify - NO SECURITY."""
        if len(signature) != self.SIG_SIZE:
            return False

        pk_seed = pk[:32]
        h = hashlib.sha256(pk_seed + message).digest()
        expected_padding = (h * 103)[:self.SIG_SIZE]
        return signature == expected_padding


def is_liboqs_available() -> bool:
    """Check if liboqs is available for production PQC signatures."""
    return _LIBOQS_AVAILABLE
