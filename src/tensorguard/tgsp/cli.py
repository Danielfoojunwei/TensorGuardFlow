import argparse
import sys
import os
from . import spec, crypto, manifest, container
from .service import TGSPService

def create_tgsp(args):
    try:
        pid = TGSPService.create_package(
            out_path=args.out,
            signing_key_path=args.producer_signing_key,
            payloads=args.payload,
            policy_path=args.policy,
            recipients=args.recipient,
            evidence_report=args.evidence_report,
            base_models=args.compat_base_model_id
        )
        print(f"Package created successfully. ID: {pid}")
    except Exception as e:
        print(f"Error creating package: {e}")
        sys.exit(1)

def verify_tgsp(args):
    print(f"Verifying: {args.in_file}")
    ok, msg = TGSPService.verify_package(args.in_file)
    if ok:
        print(f"Verification: PASS ({msg})")
        return True
    else:
        print(f"Verification: FAIL ({msg})")
        return False

def inspect_tgsp(args):
    with container.TGSPContainer(args.in_file, 'r') as z:
        m = manifest.PackageManifest.from_cbor(z.read_file(spec.MANIFEST_PATH))
        print(f"Package ID: {m.package_id}")
        print(f"Producer:   {m.producer_id}")
        print(f"Created:    {m.created_at}")
        print(f"Policy:     {m.policy_id} (v{m.policy_version})")
        print("\nPayloads:")
        for p in m.payloads:
            print(f"  - {p.payload_id}: {p.filename}")

def decrypt_tgsp(args):
    try:
        TGSPService.decrypt_package(args.in_file, args.recipient_id, args.recipient_private_key, args.outdir)
        print(f"Decryption complete. Outputs in {args.outdir}")
    except Exception as e:
        print(f"Error decrypting: {e}")
        sys.exit(1)

def keygen_tgsp(args):
    # Keep keygen here as it's a CLI-first utility
    from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
    if args.type == "ed25519":
        key = ed25519.Ed25519PrivateKey.generate()
        priv = key.private_bytes_raw()
        pub = key.public_key().public_bytes_raw()
    else:
        key = x25519.X25519PrivateKey.generate()
        priv = key.private_bytes_raw()
        pub = key.public_key().public_bytes_raw()
    
    with open(args.name + ".priv", "wb") as f: f.write(priv)
    with open(args.name + ".pub", "wb") as f: f.write(pub)
    print(f"Generated {args.type} keys: {args.name}.priv/.pub")

def main():
    parser = argparse.ArgumentParser(description="TGSP 1.0 CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Keygen
    kp = subparsers.add_parser("keygen")
    kp.add_argument("--type", choices=["ed25519", "x25519"], required=True)
    kp.add_argument("--name", required=True)

    # Create
    cp = subparsers.add_parser("create")
    cp.add_argument("--out", required=True)
    cp.add_argument("--producer-signing-key")
    cp.add_argument("--compat-base-model-id", action="append")
    cp.add_argument("--payload", action="append", help="id:type:path")
    cp.add_argument("--policy")
    cp.add_argument("--recipient", action="append", help="id:keypath")
    cp.add_argument("--evidence-report")

    # Verify
    subparsers.add_parser("verify").add_argument("in_file")
    # Inspect
    subparsers.add_parser("inspect").add_argument("in_file")
    # Decrypt
    dp = subparsers.add_parser("decrypt")
    dp.add_argument("in_file")
    dp.add_argument("--recipient-id", required=True)
    dp.add_argument("--recipient-private-key", required=True)
    dp.add_argument("--outdir", required=True)

    args = parser.parse_args()
    if args.command == "keygen": keygen_tgsp(args)
    elif args.command == "create": create_tgsp(args)
    elif args.command == "verify": verify_tgsp(args)
    elif args.command == "inspect": inspect_tgsp(args)
    elif args.command == "decrypt": decrypt_tgsp(args)
    else: parser.print_help()

if __name__ == "__main__":
    main()
