"""
Post-Quantum Cryptography Module

Provides NIST-standardized post-quantum cryptographic primitives:
- ML-KEM-768 (Kyber-768): Key Encapsulation Mechanism (FIPS 203)
- ML-DSA-65 (Dilithium-3): Digital Signature Algorithm (FIPS 204)

Production Mode:
    When liboqs is installed, real cryptographic implementations are used.
    Install with: pip install tensorguard[pqc]

Development Mode:
    When liboqs is not available, functional simulators are used.
    Simulators provide API compatibility but NO cryptographic security.

Usage:
    from tensorguard.crypto.pqc import Kyber768, Dilithium3, is_pqc_production_ready

    # Check if production PQC is available
    if is_pqc_production_ready():
        print("Using production PQC with liboqs")
    else:
        print("WARNING: Using simulator mode - no security")

    # Key encapsulation
    kem = Kyber768()
    pk, sk = kem.keygen()
    shared_secret, ciphertext = kem.encap(pk)
    recovered = kem.decap(sk, ciphertext)

    # Digital signatures
    sig = Dilithium3()
    pk, sk = sig.keygen()
    signature = sig.sign(sk, b"message")
    is_valid = sig.verify(pk, b"message", signature)
"""

from .kyber import Kyber768, is_liboqs_available as _kyber_available
from .dilithium import Dilithium3, is_liboqs_available as _dilithium_available
from .agility import PostQuantumKEM, PostQuantumSig


def is_pqc_production_ready() -> bool:
    """
    Check if production-grade PQC is available.

    Returns True if liboqs is installed and both Kyber and Dilithium
    can use the real implementations.
    """
    return _kyber_available() and _dilithium_available()


__all__ = [
    "Kyber768",
    "Dilithium3",
    "PostQuantumKEM",
    "PostQuantumSig",
    "is_pqc_production_ready",
]
