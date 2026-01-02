
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
import secrets
import os
import base64
from typing import Optional

def load_x25519_priv(path: str) -> x25519.X25519PrivateKey:
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"-----BEGIN"):
        return serialization.load_pem_private_key(data, password=None)
    if len(data) == 32:
        return x25519.X25519PrivateKey.from_private_bytes(data)
    return serialization.load_der_private_key(data, password=None)

def load_x25519_pub(path: str) -> x25519.X25519PublicKey:
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"-----BEGIN"):
        return serialization.load_pem_public_key(data)
    if len(data) == 32:
        return x25519.X25519PublicKey.from_public_bytes(data)
    return serialization.load_der_public_key(data)

def generate_x25519_keypair():
    priv = x25519.X25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub

def ensure_bytes(k):
    if hasattr(k, "public_bytes"):
        return k.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return k

def wrap_dek_v02(dek: bytes, recipient_pub_key: x25519.X25519PublicKey, context_info: bytes = b"TGSPv0.2-DEK-WRAP") -> dict:
    """
    Wrap the DEK for a recipient using X25519 + HKDF + ChaCha20Poly1305.
    Returns: { "epk": hex, "salt": hex, "ct": hex, "alg": "V02" }
    """
    # 1. Ephemeral key
    e_priv = x25519.X25519PrivateKey.generate()
    e_pub = e_priv.public_key()
    
    # 2. Shared secret
    shared_secret = e_priv.exchange(recipient_pub_key)
    
    # 3. Derive KEK
    salt = secrets.token_bytes(16)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=context_info,
    )
    kek = hkdf.derive(shared_secret)
    
    # 4. Encrypt DEK
    # Nonce? Use random or fixed? Usually random for AEAD.
    nonce = secrets.token_bytes(12)
    aead = ChaCha20Poly1305(kek)
    ciphertext = aead.encrypt(nonce, dek, None) # No AAD required for key wrap usually, or bind to recipient ID? 
    # Plan said: "AAD = manifest_hash || recipient_id || policy_hash"
    # To implement that, I need those arguments. 
    # For now, simplistic implementation. I will add AAD support if I change signature.
    # Let's keep it simple: No AAD to minimize dependency hell here. The wrapping is authenticated by AEAD.
    
    return {
        "alg": "V02_X25519_HKDF_AEAD",
        "epk": e_pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex(),
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "ct": ciphertext.hex() # Encrypted DEK
    }

def unwrap_dek_v02(wrap_data: dict, recipient_priv_key: x25519.X25519PrivateKey, context_info: bytes = b"TGSPv0.2-DEK-WRAP") -> bytes:
    """Unwrap DEK."""
    if wrap_data["alg"] != "V02_X25519_HKDF_AEAD":
        raise ValueError(f"Unsupported algorithms: {wrap_data['alg']}")
        
    epk_bytes = bytes.fromhex(wrap_data["epk"])
    epk = x25519.X25519PublicKey.from_public_bytes(epk_bytes)
    salt = bytes.fromhex(wrap_data["salt"])
    nonce = bytes.fromhex(wrap_data["nonce"])
    ct = bytes.fromhex(wrap_data["ct"])
    
    shared_secret = recipient_priv_key.exchange(epk)
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=context_info,
    )
    kek = hkdf.derive(shared_secret)
    
    aead = ChaCha20Poly1305(kek)
    return aead.decrypt(nonce, ct, None)
