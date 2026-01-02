
import os
import hashlib
from typing import Tuple
from .agility import PostQuantumKEM

class Kyber768(PostQuantumKEM):
    """
    Simulated implementation of ML-KEM-768 (Kyber-768).
    
    NOTE: This is a SIMULATOR for environments where liboqs is unavailable.
    It provides correct key/ciphertext sizes and API contracts but NO security.
    It uses AES to wrap the shared secret using the public key as a symmetric key
    to allow functional correctness testing of the KEM flow.
    """
    
    NAME = "ML-KEM-768"
    PK_SIZE = 1184
    SK_SIZE = 2400
    CT_SIZE = 1088
    SS_SIZE = 32
    
    @property
    def name(self) -> str: return self.NAME
    
    @property
    def public_key_size(self) -> int: return self.PK_SIZE
    
    @property
    def ciphertext_size(self) -> int: return self.CT_SIZE

    def keygen(self) -> Tuple[bytes, bytes]:
        # Sim: sk = random, pk = hash(sk) extended
        sk = os.urandom(self.SK_SIZE)
        pk_seed = hashlib.sha256(sk).digest()
        pk = pk_seed + os.urandom(self.PK_SIZE - 32)
        return pk, sk

    def encap(self, pk: bytes) -> Tuple[bytes, bytes]:
        # Sim: ss = random. ct = encrypt(ss, key=pk_seed)
        # To make it decryptable, we treat the first 32 bytes of PK as a symmetric key
        if len(pk) != self.PK_SIZE:
             raise ValueError("Invalid Kyber-768 PK size")
             
        shared_secret = os.urandom(self.SS_SIZE)
        
        # Obfuscate SS in CT so decap can recover it (Functional Sim)
        # key = pk[:32]
        # ct = xor(ss, key) + random_padding
        
        key = pk[:32]
        masked_ss = bytes(a ^ b for a, b in zip(shared_secret, key))
        ciphertext = masked_ss + os.urandom(self.CT_SIZE - 32)
        
        return shared_secret, ciphertext

    def decap(self, sk: bytes, ct: bytes) -> bytes:
        if len(sk) != self.SK_SIZE: raise ValueError("Invalid SK size")
        if len(ct) != self.CT_SIZE: raise ValueError("Invalid CT size")
        
        # Recover PK from SK to get the masking key
        pk_seed = hashlib.sha256(sk).digest()
        key = pk_seed
        
        masked_ss = ct[:32]
        shared_secret = bytes(a ^ b for a, b in zip(masked_ss, key))
        return shared_secret
