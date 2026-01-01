import os
import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.keywrap import aes_key_wrap, aes_key_unwrap
from cryptography.exceptions import InvalidTag

def get_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def get_sha256_stream(file_path: str, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def sign_ed25519(private_key: ed25519.Ed25519PrivateKey, data: bytes) -> bytes:
    return private_key.sign(data)

def verify_ed25519(public_key: ed25519.Ed25519PublicKey, data: bytes, signature: bytes) -> bool:
    try:
        public_key.verify(signature, data)
        return True
    except:
        return False

def derive_kek(ephemeral_private: x25519.X25519PrivateKey, recipient_public: x25519.X25519PublicKey, salt: bytes = None) -> bytes:
    shared_key = ephemeral_private.exchange(recipient_public)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"TGSP-1.0-KEK-DERIVATION",
    )
    return hkdf.derive(shared_key)

def wrap_dek(kek: bytes, dek: bytes) -> bytes:
    return aes_key_wrap(kek, dek)

def unwrap_dek(kek: bytes, wrapped_dek: bytes) -> bytes:
    return aes_key_unwrap(kek, wrapped_dek)

def encrypt_payload(data: bytes, dek: bytes, cipher: str = "AES-256-GCM") -> (bytes, bytes):
    nonce = os.urandom(12)
    if cipher == "AES-256-GCM":
        aead = AESGCM(dek)
    elif cipher == "ChaCha20-Poly1305":
        aead = ChaCha20Poly1305(dek)
    else:
        raise ValueError(f"Unsupported cipher: {cipher}")
    
    ciphertext = aead.encrypt(nonce, data, None)
    return ciphertext, nonce

def decrypt_payload(ciphertext_with_tag: bytes, dek: bytes, nonce: bytes, cipher: str = "AES-256-GCM") -> bytes:
    if cipher == "AES-256-GCM":
        aead = AESGCM(dek)
    elif cipher == "ChaCha20-Poly1305":
        aead = ChaCha20Poly1305(dek)
    else:
        raise ValueError(f"Unsupported cipher: {cipher}")
    
    return aead.decrypt(nonce, ciphertext_with_tag, None)

# --- Key Loading Utilities ---

from cryptography.hazmat.primitives import serialization

def load_ed25519_priv(path):
    with open(path, 'rb') as f:
        data = f.read()
        if len(data) == 32:
            return ed25519.Ed25519PrivateKey.from_private_bytes(data)
        # Try PEM if raw fails
        return serialization.load_pem_private_key(data, password=None)

def load_ed25519_pub(path_or_bytes):
    if isinstance(path_or_bytes, str) and os.path.exists(path_or_bytes):
        with open(path_or_bytes, 'rb') as f:
            data = f.read()
    else:
        data = path_or_bytes if isinstance(path_or_bytes, bytes) else path_or_bytes.encode()

    if len(data) == 32:
        return ed25519.Ed25519PublicKey.from_public_bytes(data)
    try:
        import base64
        decoded = base64.b64decode(data)
        if len(decoded) == 32:
            return ed25519.Ed25519PublicKey.from_public_bytes(decoded)
    except: pass
    return serialization.load_pem_public_key(data)

def load_x25519_pub(path_or_data):
    if isinstance(path_or_data, str) and os.path.exists(path_or_data):
        with open(path_or_data, 'rb') as f:
            data = f.read()
    else:
        import base64
        try:
            data = base64.b64decode(path_or_data)
        except:
            data = path_or_data if isinstance(path_or_data, bytes) else path_or_data.encode()

    if len(data) == 32:
        return x25519.X25519PublicKey.from_public_bytes(data)
    return serialization.load_pem_public_key(data)

def load_x25519_priv(path):
    with open(path, 'rb') as f:
        data = f.read()
        if len(data) == 32:
            return x25519.X25519PrivateKey.from_private_bytes(data)
        return serialization.load_pem_private_key(data, password=None)
