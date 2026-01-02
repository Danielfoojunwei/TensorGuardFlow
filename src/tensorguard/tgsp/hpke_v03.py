
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
import secrets
import struct

# Constants for RFC 9180 (DHKEM(X25519, HKDF-SHA256), HKDF-SHA256, ChaCha20Poly1305)
SUITE_ID = b"HPKE-v1" # simplified suite ID for this MVP

def encap_base(pkR: x25519.X25519PublicKey, info: bytes = b"") -> tuple[bytes, bytes]:
    """
    Minimal implementations of DHKEM Encap.
    Returns (shared_secret, enc)
    """
    skE = x25519.X25519PrivateKey.generate()
    pkE = skE.public_key()
    
    enc = pkE.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    pkR_bytes = pkR.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    
    dh = skE.exchange(pkR)
    
    # KEM Context: enc || pkR
    kem_context = enc + pkR_bytes
    
    # Extract
    prk = HKDF(hashes.SHA256(), 32, None, b"eae_prk").derive(dh) 
    
    # Expand to shared_secret
    # In full HPKE, we'd derive 'key' and 'nonce' for the AEAD.
    # Here we just return a shared secret to key the AEAD directly for wrapping.
    shared_secret = HKDF(hashes.SHA256(), 32, None, SUITE_ID + b"shared_secret" + kem_context + info).derive(prk)
    
    return shared_secret, enc

def decap_base(enc: bytes, skR: x25519.X25519PrivateKey, info: bytes = b"") -> bytes:
    """Decap."""
    pkE = x25519.X25519PublicKey.from_public_bytes(enc)
    pkR = skR.public_key()
    
    dh = skR.exchange(pkE)
    
    pkR_bytes = pkR.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    kem_context = enc + pkR_bytes
    
    prk = HKDF(hashes.SHA256(), 32, None, b"eae_prk").derive(dh)
    shared_secret = HKDF(hashes.SHA256(), 32, None, SUITE_ID + b"shared_secret" + kem_context + info).derive(prk)
    
    return shared_secret

def hpke_seal(plaintext: bytes, pkR: x25519.X25519PublicKey, info: bytes = b"", aad: bytes = b"") -> dict:
    """
    Seal plaintext using HPKE Base Mode.
    """
    # 1. Encap
    shared_secret, enc = encap_base(pkR, info)
    
    # 2. Key Schedule (Simplified: just use shared_secret as AEAD key directly)
    # Real HPKE expands shared_secret into (key, base_nonce). 
    # For MVP we treat shared_secret as KEY.
    
    key = shared_secret
    nonce = secrets.token_bytes(12)
    
    aead = ChaCha20Poly1305(key)
    ct = aead.encrypt(nonce, plaintext, aad)
    
    return {
        "alg": "V03_HPKE_MVP",
        "enc": enc.hex(),
        "ct": ct.hex(),
        "nonce": nonce.hex()
    }

def hpke_open(seal_data: dict, skR: x25519.X25519PrivateKey, info: bytes = b"", aad: bytes = b"") -> bytes:
    enc = bytes.fromhex(seal_data["enc"])
    ct = bytes.fromhex(seal_data["ct"])
    nonce = bytes.fromhex(seal_data["nonce"])
    
    shared_secret = decap_base(enc, skR, info)
    
    key = shared_secret
    aead = ChaCha20Poly1305(key)
    
    return aead.decrypt(nonce, ct, aad)
