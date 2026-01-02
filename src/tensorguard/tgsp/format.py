
import struct
import json
import hashlib
from typing import IO, List, Dict, Any, Optional
from .manifest import TGSPManifest
from .payload_crypto import encrypt_stream, PayloadDecryptor
from ..evidence.canonical import canonical_bytes

# Header Schema (Canonical Dict)
# {
#   "version": "0.2" | "0.3",
#   "offsets": { "manifest": [start, len], "recipients": [start, len], "payload": [start, len], "signature": [start, len] },
#   "hashes": { "manifest": "hex", "recipients": "hex", "payload": "hex" },
#   "crypto": { "nonce_base": "hex" }
# }

class TGSPContainer:
    def __init__(self):
        pass

def write_tgsp_container(output_path: str, 
                         manifest: TGSPManifest, 
                         payload_stream: IO[bytes], 
                         recipients_data: List[Dict],
                         signing_key, # Ed25519 Private Key
                         signing_key_id: str,
                         version: str = "0.2") -> Dict:
    """
    Write TGSP Container.
    Returns the evidence event dict (TGSP_BUILT).
    """
    
    # 1. Prepare Payload Stream (Temporary/Pipe?)
    # We need to encrypt payload first to get payload_hash and nonce_base
    import tempfile
    
    # We encrypt payload to a temp file to measure size/hash
    # In real stream we might pipe, but here we need random access to write final file? 
    # Or just sequential write.
    # Structure: [Header Len][Header][Manifest][Recipients][Payload][Signature]
    # Problem: Header contains hashes. Must compute hashes first.
    
    # 1. Encrypt Payload
    payload_temp = tempfile.TemporaryFile()
    import secrets
    dek = secrets.token_bytes(32)
    
    # We need manifest_hash and recipients_hash for AAD *during* encryption?
    # Yes, per spec.
    manifest_bytes = manifest.canonical_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    
    recipients_bytes = canonical_bytes(recipients_data)
    recipients_hash = hashlib.sha256(recipients_bytes).hexdigest()
    
    # Encrypt
    nonce_base_hex = encrypt_stream(payload_stream, payload_temp, dek, manifest_hash, recipients_hash)
    
    # Rewind temp to read for hashing? Or we can hash while encrypting?
    # encrypt_stream only returned nonce. We need to hash the ciphertext.
    payload_temp.seek(0)
    p_hasher = hashlib.sha256()
    while True:
        chunk = payload_temp.read(8192)
        if not chunk: break
        p_hasher.update(chunk)
    payload_hash = p_hasher.hexdigest()
    
    # Update manifest payload_hash? (If v0.1 compressed hash). 
    # For v0.2 encrypted, manifest usually stores plaintext hash (content_index)? 
    # Spec said "Manifest required fields: payload_hash".
    # Typically this creates circular dependency if Manifest contains PayloadHash, but PayloadAAD uses ManifestHash.
    # Resolution: Manifest contains *Plaintext* Checksums (Content Index). 
    # Header contains Encrypted Payload Hash.
    # The AAD binds Manifest Hash.
    
    manifest.payload_hash = payload_hash # Wait, we just calculated it using manifest_hash AAD?
    # Circular!
    # Plan Section 3.3: "payload_hash = sha256(payload.enc bytes)"
    # AAD includes manifest_hash.
    # Manifest itself cannot include payload_hash (of ciphertext) if ciphertext depends on manifest.
    # So manifest.payload_hash should be NULL or Plaintext Hash in v0.2?
    # Let's set manifest.payload_hash to "Pending" or handle it in Header ONLY.
    # But Manifest is signed.
    # Standard: content_index hashes are enough for integrity of files.
    # payload_hash in Header ensures ciphertext integrity.
    
    # 2. Build Header
    header = {
        "tgsp_version": version,
        "hashes": {
            "manifest": manifest_hash,
            "recipients": recipients_hash,
            "payload": payload_hash
        },
        "crypto": {
            "nonce_base": nonce_base_hex,
            "payload_alg": "CHACHA20_POLY1305"
        }
    }
    header_bytes = canonical_bytes(header)
    
    # 3. Sign Header
    from ..evidence.signing import sign_event
    # We construct a signable object: The Header.
    # Actually prompt says: "Signature covers canonical bytes of: header ... manifest ... recipients ... payload_hash"
    # If Header contains hashes of all these, signing Header is sufficient.
    sig_payload = header.copy()
    # Sign
    from cryptography.hazmat.primitives.asymmetric import ed25519
    import base64
    if signing_key:
        sig = signing_key.sign(header_bytes)
        sig_block = {
            "key_id": signing_key_id,
            "alg": "ed25519",
            "sig": base64.b64encode(sig).decode()
        }
    else:
        sig_block = {}
        
    sig_bytes = canonical_bytes(sig_block)
    
    # 4. Write
    # Offsets? Header needs offsets.
    # Length of Header?
    # We can just write chunks: [Len u32][Chunk]...
    # Simple Format:
    # [Magic TGSP][Version u16][Header Len u32][Header Bytes]
    # [Manifest Len u32][Manifest Bytes]
    # [Recipients Len u32][Recipients Bytes]
    # [Payload Len u64][Payload Bytes]
    # [Sig Len u32][Sig Bytes]
    
    with open(output_path, "wb") as f:
        f.write(b"TGSP")
        f.write(struct.pack(">H", int(version.split('.')[-1]))) # 2 or 3
        
        # Header
        f.write(struct.pack(">I", len(header_bytes)))
        f.write(header_bytes)
        
        # Manifest
        f.write(struct.pack(">I", len(manifest_bytes)))
        f.write(manifest_bytes)
        
        # Recipients
        f.write(struct.pack(">I", len(recipients_bytes)))
        f.write(recipients_bytes)
        
        # Payload
        payload_temp.seek(0, 2)
        p_len = payload_temp.tell()
        f.write(struct.pack(">Q", p_len))
        payload_temp.seek(0)
        import shutil
        shutil.copyfileobj(payload_temp, f)
        
        # Sig
        f.write(struct.pack(">I", len(sig_bytes)))
        f.write(sig_bytes)
        
    payload_temp.close()
    
    return {
        "event_type": "TGSP_BUILT",
        "subject": {"tgsp_ref": output_path, "model_ref": manifest.model_name},
        "manifest_hash": manifest_hash,
        "payload_hash": payload_hash,
        "key_id": signing_key_id
    }

def read_tgsp_header(path: str) -> dict:
    """Read just the header/manifest/recipients structures."""
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"TGSP": raise ValueError("Invalid Magic")
        version = struct.unpack(">H", f.read(2))[0]
        
        h_len = struct.unpack(">I", f.read(4))[0]
        header = json.loads(f.read(h_len))
        
        m_len = struct.unpack(">I", f.read(4))[0]
        manifest = json.loads(f.read(m_len))
        
        r_len = struct.unpack(">I", f.read(4))[0]
        recipients = json.loads(f.read(r_len))
        
        return {
            "version": f"0.{version}",
            "header": header,
            "manifest": manifest,
            "recipients": recipients,
            "payload_offset": f.tell() + 8 # Skip payload len (8 bytes)
        }
