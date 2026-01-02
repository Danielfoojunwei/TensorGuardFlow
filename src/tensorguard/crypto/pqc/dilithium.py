
import os
import hashlib
from typing import Tuple
from .agility import PostQuantumSig

class Dilithium3(PostQuantumSig):
    """
    Simulated implementation of ML-DSA-65 (Dilithium-3).
    """
    
    NAME = "ML-DSA-65"
    PK_SIZE = 1952
    SK_SIZE = 4032
    SIG_SIZE = 3293
    
    @property
    def name(self) -> str: return self.NAME

    def keygen(self) -> Tuple[bytes, bytes]:
        sk = os.urandom(self.SK_SIZE)
        pk_seed = hashlib.sha256(sk).digest()
        pk = pk_seed + os.urandom(self.PK_SIZE - 32)
        return pk, sk

    def sign(self, sk: bytes, message: bytes) -> bytes:
        # Sim: Sig = Hash(sk + message) restricted to size?
        # To verify, we need to relate it to PK.
        # Verify checks: Hash(sk_from_pk? no)
        
        # Sim logic: Sig = Hash(pk_seed || message) + padding
        # But verify only has PK.
        # PK contains pk_seed (first 32 bytes).
        
        pk_seed = hashlib.sha256(sk).digest()
        h = hashlib.sha256(pk_seed + message).digest()
        
        # Deterministic padding to fill SIG_SIZE
        padding = (h * 103)[:self.SIG_SIZE]
        return padding

    def verify(self, pk: bytes, message: bytes, signature: bytes) -> bool:
        if len(pk) != self.PK_SIZE: return False
        if len(signature) != self.SIG_SIZE: return False
        
        pk_seed = pk[:32]
        h = hashlib.sha256(pk_seed + message).digest()
        expected_padding = (h * 103)[:self.SIG_SIZE]
        
        return signature == expected_padding
