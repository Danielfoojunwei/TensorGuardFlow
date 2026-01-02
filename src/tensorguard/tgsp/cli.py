import argparse
import sys
import json
import os
import secrets
import struct
import hashlib
import tarfile
import tempfile
from typing import List, Dict

from .manifest import PackageManifest
from .tar_deterministic import create_deterministic_tar
from .format import write_tgsp_container, read_tgsp_header
from .wrap_v02 import wrap_dek_v02, unwrap_dek_v02, generate_x25519_keypair, load_x25519_priv, load_x25519_pub
from .hpke_v03 import hpke_seal, hpke_open
from .payload_crypto import PayloadDecryptor
from ..evidence.signing import generate_keypair, load_private_key, load_public_key
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

def run_keygen(args):
    out = args.out
    os.makedirs(out, exist_ok=True)
    
    if args.type == "signing":
        priv, pub = generate_keypair()
        with open(os.path.join(out, "signing.priv"), "wb") as f:
            f.write(priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        with open(os.path.join(out, "signing.pub"), "wb") as f:
            f.write(pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        print(f"Generated signing key in {out}")
        
    elif args.type == "x25519":
        priv, pub = generate_x25519_keypair()
        with open(os.path.join(out, "encryption.priv"), "wb") as f:
            f.write(priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
        with open(os.path.join(out, "encryption.pub"), "wb") as f:
            f.write(pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        print(f"Generated x25519 key in {out}")

def run_build(args):
    # 1. Manifest
    manifest = PackageManifest(
        tgsp_version=args.tgsp_version,
        package_id=secrets.token_hex(8),
        model_name=args.model_name,
        model_version=args.model_version,
        author_id="cli-user",
        payload_hash="pending"
    )
    
    # 2. Recipients & keys
    recipients_data = []
    dek = secrets.token_bytes(32)
    
    if args.recipients:
        for r_str in args.recipients:
            # format: fleet:id:path
            parts = r_str.split(':', 2)
            if len(parts) < 3: continue
            rid = f"{parts[0]}:{parts[1]}"
            path = parts[2]
            
            pub_key = load_x25519_pub(path)
            
            if args.tgsp_version == "0.2":
                wrap = wrap_dek_v02(dek, pub_key)
                recipients_data.append({"recipient_id": rid, "wrap": wrap})
            else: # 0.3
                seal = hpke_seal(dek, pub_key)
                recipients_data.append({"recipient_id": rid, "hpke": seal})
         
    # 3. Payload Stream (Tar)
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        create_deterministic_tar(args.input_dir, tf.name)
        tf_path = tf.name
        
    # 4. Sign
    if args.signing_key:
        sk = load_private_key(args.signing_key)
        sk_id = "key_1"
        import base64
        manifest.producer_pubkey_ed25519 = base64.b64encode(sk.public_key().public_bytes_raw()).decode()
    else:
        sk = None
        sk_id = "none"
        
    # 5. Write Container
    with open(tf_path, "rb") as payload_stream:
        evt = write_tgsp_container(args.out, manifest, payload_stream, recipients_data, dek, sk, sk_id, args.tgsp_version)
        
    from ..evidence.store import get_store
    store = get_store()
    store.save_event(evt)
    
    os.unlink(tf_path)
    print(f"TGSP Built: {args.out}")
    print(json.dumps(evt, indent=2))

def run_inspect(args):
    data = read_tgsp_header(args.file)
    print(json.dumps(data["manifest"], indent=2))
    print("Recipients:", len(data["recipients"]))

def run_open(args):
    data = read_tgsp_header(args.file)
    
    my_rid = args.recipient_id
    rec = next((r for r in data["recipients"] if r["recipient_id"] == my_rid), None)
    if not rec:
        print(f"Recipient {my_rid} not found")
        return
        
    sk = load_x25519_priv(args.key)
    
    if "wrap" in rec: # v0.2
        dek = unwrap_dek_v02(rec["wrap"], sk)
    else: # v0.3
        dek = hpke_open(rec["hpke"], sk)
        
    # Decrypt Payload
    h = data["header"]
    nonce_base = bytes.fromhex(h["crypto"]["nonce_base"])
    m_hash = h["hashes"]["manifest"]
    r_hash = h["hashes"]["recipients"]
    
    decryptor = PayloadDecryptor(dek, nonce_base, m_hash, r_hash)
    
    os.makedirs(args.out_dir, exist_ok=True)
    out_tar = os.path.join(args.out_dir, "payload_decrypted_temp.tar")
    
    with open(args.file, "rb") as f:
        f.seek(data["payload_offset"])
        total_read = 0
        with open(out_tar, "wb") as out_f:
            while total_read < data["payload_len"]:
                chunk = decryptor.decrypt_chunk_from_stream(f)
                if not chunk: break
                out_f.write(chunk)
                total_read += (4 + len(chunk) + 16)
        
    # Untar and cleanup
    try:
        with tarfile.open(out_tar, "r") as tr:
            tr.extractall(args.out_dir)
        os.remove(out_tar)
        print(f"Payload decrypted and extracted to {args.out_dir}")
    except Exception as e:
        print(f"Payload decrypted to {out_tar} (Extraction failed: {e})")

# --- Legacy Shims for Backward Compatibility ---
def create_tgsp(args):
    import shutil
    with tempfile.TemporaryDirectory() as tmp_in:
        if hasattr(args, 'payload') and args.payload:
            for p in args.payload:
                parts = p.split(':')
                if len(parts) == 3:
                    shutil.copy(parts[2], os.path.join(tmp_in, os.path.basename(parts[2])))
        
        new_args = argparse.Namespace(
            input_dir=tmp_in,
            out=args.out,
            tgsp_version="0.2",
            model_name="legacy-model",
            model_version="0.0.1",
            recipients=[],
            signing_key=getattr(args, 'producer_signing_key', None)
        )
        if hasattr(args, 'recipient') and args.recipient:
            new_args.recipients = [f"legacy:{r}" for r in args.recipient]
        run_build(new_args)

def verify_tgsp(args):
    try:
        from .format import verify_tgsp_container
        return verify_tgsp_container(args.in_file)
    except Exception:
        return False

def decrypt_tgsp(args):
    new_args = argparse.Namespace(
        file=args.in_file,
        recipient_id=f"legacy:{args.recipient_id}",
        key=args.recipient_private_key,
        out_dir=args.outdir
    )
    run_open(new_args)

def main():
    parser = argparse.ArgumentParser()
    subps = parser.add_subparsers(dest="cmd")
    
    kg = subps.add_parser("keygen")
    kg.add_argument("--type", choices=["signing", "x25519"])
    kg.add_argument("--out", required=True)
    
    bd = subps.add_parser("build")
    bd.add_argument("--input-dir", required=True)
    bd.add_argument("--out", required=True)
    bd.add_argument("--tgsp-version", choices=["0.2", "0.3"], default="0.2")
    bd.add_argument("--model-name", default="unknown")
    bd.add_argument("--model-version", default="0.0.1")
    bd.add_argument("--recipients", nargs="+")
    bd.add_argument("--signing-key")
    
    ins = subps.add_parser("inspect")
    ins.add_argument("--file", required=True)
    
    op = subps.add_parser("open")
    op.add_argument("--file", required=True)
    op.add_argument("--recipient-id", required=True)
    op.add_argument("--key", required=True)
    op.add_argument("--out-dir", required=True)
    
    args = parser.parse_args()
    if args.cmd == "keygen": run_keygen(args)
    elif args.cmd == "build": run_build(args)
    elif args.cmd == "inspect": run_inspect(args)
    elif args.cmd == "open": run_open(args)
    else: parser.print_help()

if __name__ == "__main__":
    main()
