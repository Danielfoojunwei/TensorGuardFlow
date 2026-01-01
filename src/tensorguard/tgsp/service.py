import os
import base64
import cbor2
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from . import spec, crypto, manifest, policy, container

class TGSPService:
    @staticmethod
    def create_package(out_path, signing_key_path=None, payloads=None, policy_path=None, recipients=None, evidence_report=None, base_models=None):
        """
        id:type:path for payloads
        id:pubkey_path for recipients
        """
        pkg_manifest = manifest.PackageManifest(
            base_model_ids=base_models or []
        )
        
        # 1. Signer
        priv_key = None
        if signing_key_path:
            priv_key = crypto.load_ed25519_priv(signing_key_path)
            pkg_manifest.producer_pubkey_ed25519 = base64.b64encode(priv_key.public_key().public_bytes_raw()).decode()

        # 2. Policy
        if policy_path:
            meta = policy.get_policy_metadata(policy_path)
            pkg_manifest.policy_id = meta['id']
            pkg_manifest.policy_version = meta['version']
            pkg_manifest.policy_hash = crypto.get_sha256_stream(policy_path)

        # 3. Payloads & Keys
        payload_data = {}
        for p_str in (payloads or []):
            pid, ptype, ppath = p_str.split(":", 2)
            dek = os.urandom(32)
            payload_data[pid] = (ppath, dek, ptype, os.path.basename(ppath))

        with container.TGSPContainer(out_path, mode='w') as z:
            # Policy file
            if policy_path:
                with open(policy_path, 'rb') as f:
                    z.write_file(spec.POLICY_PATH, f.read())
                z.write_file(spec.POLICY_HASH_PATH, pkg_manifest.policy_hash.encode())

            # Evidence
            if evidence_report:
                h = crypto.get_sha256_stream(evidence_report)
                fname = os.path.basename(evidence_report)
                with open(evidence_report, 'rb') as f:
                    z.write_file(f"{spec.EVIDENCE_DIR}/{fname}", f.read())
                pkg_manifest.evidence.append(manifest.EvidenceDescriptor("json", fname, h))

            # Encrypt and Write Payloads
            for pid, (ppath, dek, ptype, fname) in payload_data.items():
                with open(ppath, 'rb') as f:
                    content = f.read()
                
                enc_data, nonce = crypto.encrypt_payload(content, dek)
                final_payload = nonce + enc_data
                payload_arc = f"{spec.PAYLOAD_DIR}/{pid}.enc"
                z.write_file(payload_arc, final_payload)
                
                enc_hash = crypto.get_sha256(final_payload)
                plain_hash = crypto.get_sha256(content)
                z.write_file(f"{payload_arc}.hash", enc_hash.encode())
                
                pkg_manifest.payloads.append(manifest.PayloadDescriptor(
                    payload_id=pid, logical_type=ptype, filename=fname,
                    enc_hash=enc_hash, plaintext_hash=plain_hash
                ))

            # Recipient Envelopes
            ephemeral_priv = x25519.X25519PrivateKey.generate()
            recipient_info = {
                "producer_ephemeral_pubkey": base64.b64encode(ephemeral_priv.public_key().public_bytes_raw()).decode(),
                "recipients": []
            }
            
            for r_str in (recipients or []):
                rid, rkey_path = r_str.split(":", 1)
                r_pub = crypto.load_x25519_pub(rkey_path)
                kek = crypto.derive_kek(ephemeral_priv, r_pub)
                
                wrapped_deks = {pid: base64.b64encode(crypto.wrap_dek(kek, dek)).decode() 
                               for pid, (_, dek, _, _) in payload_data.items()}
                
                recipient_info["recipients"].append({"recipient_id": rid, "wrapped_deks": wrapped_deks})
            
            z.write_file(spec.RECIPIENTS_PATH, cbor2.dumps(recipient_info))

            # Finalize Manifest
            pkg_manifest.file_inventory = z.get_inventory_hashes()
            manifest_bytes = pkg_manifest.to_canonical_cbor()
            z.write_file(spec.MANIFEST_PATH, manifest_bytes)
            
            if priv_key:
                sig = crypto.sign_ed25519(priv_key, manifest_bytes)
                z.write_file(spec.SIGNATURE_PATH, sig)

        return pkg_manifest.package_id

    @staticmethod
    def verify_package(path):
        with container.TGSPContainer(path, mode='r') as z:
            m_bytes = z.read_file(spec.MANIFEST_PATH)
            m = manifest.PackageManifest.from_cbor(m_bytes)
            
            # 1. Integrity check (All files in manifest must match)
            current_inventory = z.get_inventory_hashes()
            for p, h in m.file_inventory.items():
                if current_inventory.get(p) != h: 
                    return False, f"Hash mismatch: {p}"
            
            # 2. Strict whitelist check (No extra files allowed unless in META/)
            for name in z.list_files():
                if name.startswith("META/"): continue
                if name not in m.file_inventory:
                    return False, f"Unregistered file detected: {name}"

            # 3. Signature
            if spec.SIGNATURE_PATH in z.list_files():
                sig = z.read_file(spec.SIGNATURE_PATH)
                pub = crypto.load_ed25519_pub(m.producer_pubkey_ed25519)
                if not crypto.verify_ed25519(pub, m_bytes, sig):
                    return False, "Signature invalid"
            
            return True, "OK"

    @staticmethod
    def decrypt_package(path, recipient_id, priv_key_path, out_dir):
        abs_out_dir = os.path.abspath(out_dir)
        os.makedirs(abs_out_dir, exist_ok=True)
        
        with container.TGSPContainer(path, 'r') as z:
            m = manifest.PackageManifest.from_cbor(z.read_file(spec.MANIFEST_PATH))
            recipients = cbor2.loads(z.read_file(spec.RECIPIENTS_PATH))
            
            entry = next((r for r in recipients['recipients'] if r['recipient_id'] == recipient_id), None)
            if not entry: raise ValueError("Recipient not found")
            
            priv_key = crypto.load_x25519_priv(priv_key_path)
            producer_pub = crypto.load_x25519_pub(recipients['producer_ephemeral_pubkey'])
            kek = crypto.derive_kek(priv_key, producer_pub)
            
            for p in m.payloads:
                wrapped_dek = entry['wrapped_deks'].get(p.payload_id)
                if not wrapped_dek: continue
                
                dek = crypto.unwrap_dek(kek, base64.b64decode(wrapped_dek))
                raw = z.read_file(f"{spec.PAYLOAD_DIR}/{p.payload_id}.enc")
                plaintext = crypto.decrypt_payload(raw[12:], dek, raw[:12], p.cipher)
                
                if crypto.get_sha256(plaintext) != p.plaintext_hash:
                    raise ValueError(f"Integrity failure on {p.payload_id}")
                
                # Path Traversal Protection
                if ".." in p.filename or p.filename.startswith("/") or p.filename.startswith("\\"):
                    raise ValueError(f"Malicious filename detected in manifest: {p.filename}")
                
                safe_filename = os.path.basename(p.filename) 
                out_path = os.path.normpath(os.path.join(abs_out_dir, safe_filename))
                
                if not out_path.startswith(abs_out_dir):
                    raise ValueError(f"Malicious filename path resolution failure: {p.filename}")

                with open(out_path, 'wb') as f:
                    f.write(plaintext)
            return True
