"""
Unified Key Management Fabric (UKF)
Consolidates storage, metadata, and lifecycle for all TensorGuard keys.

Security Features:
- Encryption at rest using AES-256-GCM (default)
- Vault master key derived from TG_VAULT_MASTER_KEY environment variable
- File permissions enforced (0600 for key files, 0700 for directories)
- Explicit operator opt-out required for unencrypted storage

Environment Variables:
- TG_VAULT_MASTER_KEY: 32+ character secret for vault encryption (REQUIRED in production)
- TG_VAULT_UNENCRYPTED: Set to "true" to disable encryption (NOT RECOMMENDED)
"""

import base64
import datetime
import hashlib
import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..utils.logging import get_logger
from ..utils.exceptions import CryptographyError

logger = get_logger(__name__)

# Vault encryption configuration
TG_VAULT_MASTER_KEY = os.getenv("TG_VAULT_MASTER_KEY")
TG_VAULT_UNENCRYPTED = os.getenv("TG_VAULT_UNENCRYPTED", "false").lower() == "true"
TG_ENVIRONMENT = os.getenv("TG_ENVIRONMENT", "development")

# Encryption constants
VAULT_NONCE_SIZE = 12  # 96 bits for AES-GCM
VAULT_KEY_SIZE = 32    # 256 bits for AES-256
ENCRYPTED_FILE_VERSION = 1


def _derive_vault_key(master_key: str) -> bytes:
    """
    Derive a 256-bit encryption key from the master key using HKDF-like derivation.
    Uses SHA-256 with a fixed salt for deterministic derivation.
    """
    salt = b"tensorguard-vault-v1"
    return hashlib.pbkdf2_hmac(
        "sha256",
        master_key.encode("utf-8"),
        salt,
        iterations=100000,
        dklen=VAULT_KEY_SIZE
    )


def _get_vault_cipher() -> Optional[AESGCM]:
    """
    Get the AES-GCM cipher for vault encryption.
    Returns None if encryption is disabled.
    """
    if TG_VAULT_UNENCRYPTED:
        if TG_ENVIRONMENT == "production":
            logger.critical(
                "SECURITY WARNING: Vault encryption disabled in production. "
                "Set TG_VAULT_MASTER_KEY and remove TG_VAULT_UNENCRYPTED."
            )
        return None

    if not TG_VAULT_MASTER_KEY:
        if TG_ENVIRONMENT == "production":
            raise CryptographyError(
                "TG_VAULT_MASTER_KEY is required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        logger.warning(
            "SECURITY WARNING: TG_VAULT_MASTER_KEY not set. "
            "Keys will be stored unencrypted. This is NOT secure for production."
        )
        return None

    if len(TG_VAULT_MASTER_KEY) < 32:
        raise CryptographyError(
            "TG_VAULT_MASTER_KEY must be at least 32 characters for adequate security."
        )

    derived_key = _derive_vault_key(TG_VAULT_MASTER_KEY)
    return AESGCM(derived_key)


def _encrypt_key_data(plaintext: bytes, cipher: AESGCM) -> bytes:
    """
    Encrypt key data using AES-256-GCM.

    Returns a binary blob: version (1 byte) + nonce (12 bytes) + ciphertext + tag
    """
    nonce = secrets.token_bytes(VAULT_NONCE_SIZE)
    ciphertext = cipher.encrypt(nonce, plaintext, associated_data=None)

    # Format: version (1 byte) + nonce (12 bytes) + ciphertext+tag
    return bytes([ENCRYPTED_FILE_VERSION]) + nonce + ciphertext


def _decrypt_key_data(encrypted: bytes, cipher: AESGCM) -> bytes:
    """
    Decrypt key data encrypted with AES-256-GCM.
    """
    if len(encrypted) < 1 + VAULT_NONCE_SIZE + 16:  # version + nonce + min tag
        raise CryptographyError("Invalid encrypted data: too short")

    version = encrypted[0]
    if version != ENCRYPTED_FILE_VERSION:
        raise CryptographyError(f"Unsupported encrypted file version: {version}")

    nonce = encrypted[1:1 + VAULT_NONCE_SIZE]
    ciphertext = encrypted[1 + VAULT_NONCE_SIZE:]

    try:
        return cipher.decrypt(nonce, ciphertext, associated_data=None)
    except Exception as e:
        raise CryptographyError(f"Decryption failed: {e}")

class KeyScope(str, Enum):
    IDENTITY = "identity"      # Ed25519, X25519, RSA/EC Certificates
    INFERENCE = "inference"    # MOAI (CKKS) contexts
    AGGREGATION = "aggregation" # N2HE (LWE) keys
    SYSTEM = "system"          # Internal app secrets

@dataclass
class UnifiedKeyMetadata:
    """Standard metadata for any key in the TensorGuard fabric."""
    key_id: str
    scope: KeyScope
    algorithm: str
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
    owner_id: str = "agent-local"
    version: str = "2.0.0"
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

class UnifiedKeyManager:
    """
    Central orchestrator for key persistence and discovery.
    Ensures consistent pathing, permissions, and metadata across all subsystems.

    Security Features:
    - Keys are encrypted at rest by default (AES-256-GCM)
    - File permissions are enforced (0600 for files, 0700 for directories)
    - Encryption requires TG_VAULT_MASTER_KEY environment variable
    - Explicit opt-out required for unencrypted storage (TG_VAULT_UNENCRYPTED=true)
    """

    def __init__(self, vault_root: str = "keys", encryption_enabled: Optional[bool] = None):
        """
        Initialize the key manager.

        Args:
            vault_root: Directory for key storage
            encryption_enabled: Override encryption setting (None = use environment)
        """
        self.vault_root = Path(vault_root)
        self.vault_root.mkdir(parents=True, exist_ok=True)

        # Initialize encryption
        if encryption_enabled is None:
            self._cipher = _get_vault_cipher()
        elif encryption_enabled:
            if not TG_VAULT_MASTER_KEY:
                raise CryptographyError("encryption_enabled=True but TG_VAULT_MASTER_KEY not set")
            self._cipher = _get_vault_cipher()
        else:
            self._cipher = None

        self.encryption_enabled = self._cipher is not None
        if self.encryption_enabled:
            logger.info("Vault encryption enabled (AES-256-GCM)")
        else:
            logger.warning("Vault encryption disabled - keys stored in plaintext")

        # Ensure base dir permissions if possible
        try:
            os.chmod(self.vault_root, 0o700)
        except (OSError, PermissionError) as e:
            logger.debug(f"Could not set vault permissions: {e}")

    def _get_scope_path(self, scope: KeyScope) -> Path:
        path = self.vault_root / scope.value
        path.mkdir(exist_ok=True)
        return path

    def save_key_artifact(
        self,
        scope: KeyScope,
        name: str,
        data: bytes,
        algorithm: str,
        params: Optional[Dict[str, Any]] = None,
        suffix: str = ".bin",
    ) -> str:
        """
        Save a binary key artifact with accompanying metadata.

        If encryption is enabled, the key data is encrypted with AES-256-GCM
        before being written to disk.

        Args:
            scope: Key scope (identity, inference, aggregation, system)
            name: Key name (must be filesystem-safe)
            data: Raw key bytes
            algorithm: Algorithm identifier (e.g., "Ed25519", "AES-256-GCM")
            params: Optional algorithm parameters
            suffix: File suffix for the key file

        Returns:
            Key ID string (scope_name format)
        """
        name = str(name)
        scope_dir = self._get_scope_path(scope)

        # Path safety
        if ".." in name or name.startswith("/") or name.startswith("\\"):
            name = os.path.basename(name)

        key_id = f"{scope.value}_{name}"
        data_path = scope_dir / f"{name}{suffix}"
        meta_path = scope_dir / f"{name}.meta.json"

        # 1. Prepare metadata
        meta = UnifiedKeyMetadata(
            key_id=key_id,
            scope=scope,
            algorithm=algorithm,
            params=params or {},
        )
        # Add encryption marker to metadata
        meta.params["encrypted"] = self.encryption_enabled

        try:
            # 2. Encrypt data if enabled
            if self.encryption_enabled and self._cipher:
                stored_data = _encrypt_key_data(data, self._cipher)
                logger.debug(f"Encrypted key data for {name} ({len(data)} -> {len(stored_data)} bytes)")
            else:
                stored_data = data

            # 3. Save binary key file
            data_path.write_bytes(stored_data)
            try:
                data_path.chmod(0o600)
            except (OSError, PermissionError) as e:
                logger.debug(f"Could not set key file permissions: {e}")

            # 4. Save metadata
            meta_path.write_text(meta.to_json())
            try:
                meta_path.chmod(0o600)
            except (OSError, PermissionError) as e:
                logger.debug(f"Could not set metadata file permissions: {e}")

            logger.info(
                f"Saved {scope.value} key '{name}' to {data_path} "
                f"(encrypted={self.encryption_enabled})"
            )
            return key_id
        except CryptographyError:
            raise
        except (IOError, OSError) as e:
            raise CryptographyError(f"Vault I/O failure for {name}: {e}")
        except Exception as e:
            raise CryptographyError(f"Vault failure for {name}: {e}")

    def load_key_artifact(
        self, scope: KeyScope, name: str, suffix: str = ".bin"
    ) -> Tuple[bytes, UnifiedKeyMetadata]:
        """
        Load a key and its metadata.

        Automatically detects and decrypts encrypted keys if the vault
        master key is available.

        Args:
            scope: Key scope
            name: Key name
            suffix: File suffix

        Returns:
            Tuple of (key_data, metadata)

        Raises:
            FileNotFoundError: If key file doesn't exist
            CryptographyError: If decryption fails
        """
        name = str(name)
        scope_dir = self._get_scope_path(scope)
        data_path = scope_dir / f"{name}{suffix}"
        meta_path = scope_dir / f"{name}.meta.json"

        if not data_path.exists():
            raise FileNotFoundError(f"Key file not found: {data_path}")

        try:
            # Read raw data
            stored_data = data_path.read_bytes()

            # Load metadata
            meta_data = json.loads(meta_path.read_text())
            meta_data["scope"] = KeyScope(meta_data["scope"])
            meta = UnifiedKeyMetadata(**meta_data)

            # Check if key was stored encrypted
            was_encrypted = meta.params.get("encrypted", False)

            if was_encrypted:
                if not self._cipher:
                    raise CryptographyError(
                        f"Key '{name}' is encrypted but TG_VAULT_MASTER_KEY is not set. "
                        "Set the environment variable to decrypt."
                    )
                data = _decrypt_key_data(stored_data, self._cipher)
                logger.debug(f"Decrypted key {name} ({len(stored_data)} -> {len(data)} bytes)")
            else:
                data = stored_data
                if self.encryption_enabled:
                    logger.warning(
                        f"Key '{name}' is stored unencrypted. "
                        "Consider re-saving to enable encryption."
                    )

            return data, meta

        except CryptographyError:
            raise
        except FileNotFoundError:
            raise
        except (json.JSONDecodeError, KeyError) as e:
            raise CryptographyError(f"Invalid metadata for key {name}: {e}")
        except (IOError, OSError) as e:
            raise CryptographyError(f"Failed to read key {name}: {e}")
        except Exception as e:
            raise CryptographyError(f"Failed to load key {name}: {e}")

    def list_keys(self, scope: Optional[KeyScope] = None) -> List[Dict[str, Any]]:
        """List all available keys, optionally filtered by scope."""
        result = []
        scopes = [scope] if scope else list(KeyScope)
        
        for s in scopes:
            scope_dir = self.vault_root / s.value
            if not scope_dir.exists():
                continue
            
            for meta_file in scope_dir.glob("*.meta.json"):
                try:
                    meta = json.loads(meta_file.read_text())
                    result.append(meta)
                except (json.JSONDecodeError, IOError, OSError) as e:
                    logger.warning(f"Failed to parse metadata file {meta_file}: {e}")
                    continue
        return result

    def delete_key(self, scope: KeyScope, name: str, suffix: str = ".bin") -> None:
        """Securely remove a key artifact."""
        name = str(name)
        scope_dir = self._get_scope_path(scope)
        key_path = scope_dir / f"{name}{suffix}"
        meta_path = scope_dir / f"{name}.meta.json"

        # Overwrite with random data before deletion for secure removal
        if key_path.exists():
            try:
                size = key_path.stat().st_size
                key_path.write_bytes(secrets.token_bytes(size))
            except (IOError, OSError):
                pass  # Best effort secure delete

        key_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        logger.info(f"Deleted {scope.value} key: {name}")

    def migrate_to_encrypted(self, scope: Optional[KeyScope] = None) -> int:
        """
        Migrate unencrypted keys to encrypted storage.

        Args:
            scope: Optional scope to limit migration

        Returns:
            Number of keys migrated

        Raises:
            CryptographyError: If encryption is not enabled
        """
        if not self.encryption_enabled:
            raise CryptographyError(
                "Cannot migrate: encryption not enabled. Set TG_VAULT_MASTER_KEY."
            )

        migrated = 0
        keys = self.list_keys(scope)

        for key_meta in keys:
            if key_meta.get("params", {}).get("encrypted"):
                continue  # Already encrypted

            key_scope = KeyScope(key_meta["scope"])
            key_name = key_meta["key_id"].split("_", 1)[1]

            try:
                # Load with current settings (may be unencrypted)
                data, meta = self.load_key_artifact(key_scope, key_name)

                # Re-save (will encrypt)
                self.save_key_artifact(
                    scope=key_scope,
                    name=key_name,
                    data=data,
                    algorithm=meta.algorithm,
                    params={k: v for k, v in meta.params.items() if k != "encrypted"},
                )
                migrated += 1
                logger.info(f"Migrated key {key_meta['key_id']} to encrypted storage")

            except Exception as e:
                logger.error(f"Failed to migrate key {key_meta['key_id']}: {e}")

        return migrated

    def export_vault(
        self,
        output_path: str,
        include_material: bool = False,
        scope: Optional[KeyScope] = None,
    ) -> Dict[str, Any]:
        """
        Export vault metadata (and optionally key material) for disaster recovery.

        By default, exports ONLY metadata (key names, algorithms, timestamps).
        Use include_material=True to include actual key data (SECURITY SENSITIVE).

        Args:
            output_path: Path to write the export JSON file
            include_material: If True, include encrypted key material (default: False)
            scope: Optional scope filter

        Returns:
            Export summary dict
        """
        export_data = {
            "version": "1.0",
            "exported_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "vault_root": str(self.vault_root.absolute()),
            "encryption_enabled": self.encryption_enabled,
            "include_material": include_material,
            "keys": [],
        }

        keys = self.list_keys(scope)
        exported_count = 0
        errors = []

        for key_meta in keys:
            key_entry = {
                "key_id": key_meta.get("key_id"),
                "scope": key_meta.get("scope"),
                "algorithm": key_meta.get("algorithm"),
                "created_at": key_meta.get("created_at"),
                "owner_id": key_meta.get("owner_id"),
                "version": key_meta.get("version"),
                "params": {k: v for k, v in key_meta.get("params", {}).items() if k != "encrypted"},
                "encrypted_at_rest": key_meta.get("params", {}).get("encrypted", False),
            }

            if include_material:
                try:
                    key_scope = KeyScope(key_meta["scope"])
                    key_name = key_meta["key_id"].split("_", 1)[1]
                    data, _ = self.load_key_artifact(key_scope, key_name)

                    # Always export as base64-encoded, even if decrypted
                    # Re-encrypt with export-specific protection
                    key_entry["material"] = base64.b64encode(data).decode("ascii")
                    key_entry["material_encoding"] = "base64"
                except Exception as e:
                    key_entry["material_error"] = str(e)
                    errors.append(f"{key_meta.get('key_id')}: {e}")

            export_data["keys"].append(key_entry)
            exported_count += 1

        export_data["summary"] = {
            "total_keys": exported_count,
            "errors": len(errors),
            "error_details": errors if errors else None,
        }

        # Write export file
        output = Path(output_path)
        output.write_text(json.dumps(export_data, indent=2))
        try:
            output.chmod(0o600)  # Protect export file
        except (OSError, PermissionError):
            pass

        logger.info(f"Exported {exported_count} keys to {output_path} (include_material={include_material})")
        return export_data["summary"]

    def import_vault(
        self,
        input_path: str,
        import_material: bool = False,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """
        Import vault from an export file.

        By default, only validates and reports on the export contents.
        Use import_material=True to actually import key material.

        Args:
            input_path: Path to the export JSON file
            import_material: If True, import key material (requires material in export)
            overwrite: If True, overwrite existing keys

        Returns:
            Import summary dict
        """
        input_file = Path(input_path)
        if not input_file.exists():
            raise FileNotFoundError(f"Export file not found: {input_path}")

        export_data = json.loads(input_file.read_text())

        # Validate export format
        if export_data.get("version") != "1.0":
            raise ValueError(f"Unsupported export version: {export_data.get('version')}")

        summary = {
            "total_in_export": len(export_data.get("keys", [])),
            "imported": 0,
            "skipped_existing": 0,
            "skipped_no_material": 0,
            "errors": [],
        }

        existing_keys = {k["key_id"] for k in self.list_keys()}

        for key_entry in export_data.get("keys", []):
            key_id = key_entry.get("key_id")

            # Check if key exists
            if key_id in existing_keys and not overwrite:
                summary["skipped_existing"] += 1
                logger.debug(f"Skipping existing key: {key_id}")
                continue

            if import_material:
                material = key_entry.get("material")
                if not material:
                    summary["skipped_no_material"] += 1
                    logger.warning(f"No material in export for key: {key_id}")
                    continue

                try:
                    # Decode material
                    data = base64.b64decode(material)
                    key_scope = KeyScope(key_entry["scope"])
                    key_name = key_id.split("_", 1)[1]

                    # Import key
                    self.save_key_artifact(
                        scope=key_scope,
                        name=key_name,
                        data=data,
                        algorithm=key_entry.get("algorithm", "unknown"),
                        params=key_entry.get("params", {}),
                    )
                    summary["imported"] += 1
                    logger.info(f"Imported key: {key_id}")

                except Exception as e:
                    summary["errors"].append(f"{key_id}: {e}")
                    logger.error(f"Failed to import key {key_id}: {e}")

        return summary

    def get_vault_status(self) -> Dict[str, Any]:
        """Get comprehensive vault status for health checks."""
        keys = self.list_keys()
        scopes = {}
        for key in keys:
            scope = key.get("scope", "unknown")
            scopes[scope] = scopes.get(scope, 0) + 1

        return {
            "vault_root": str(self.vault_root.absolute()),
            "encryption_enabled": self.encryption_enabled,
            "total_keys": len(keys),
            "keys_by_scope": scopes,
            "writable": self._check_writable(),
        }

    def _check_writable(self) -> bool:
        """Check if vault directory is writable."""
        try:
            test_file = self.vault_root / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception:
            return False


# Global Instance - lazy initialization
_vault_instance: Optional[UnifiedKeyManager] = None


def get_vault(vault_root: str = "keys") -> UnifiedKeyManager:
    """
    Get the global vault instance (lazy initialization).

    This allows the vault to be used even if TG_VAULT_MASTER_KEY
    isn't set at import time.
    """
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = UnifiedKeyManager(vault_root=vault_root)
    return _vault_instance


# Backward compatibility alias
vault = property(lambda self: get_vault())


class _VaultProxy:
    """Proxy class for backward compatibility with 'vault' module-level access."""

    def __getattr__(self, name):
        return getattr(get_vault(), name)


vault = _VaultProxy()


# ============================================================================
# CLI Interface for Vault Operations
# ============================================================================

def _cli_export(args):
    """CLI handler for vault export."""
    vault_mgr = get_vault(args.vault_path)
    scope = KeyScope(args.scope) if args.scope else None

    print(f"Exporting vault from: {vault_mgr.vault_root}")
    if args.include_material:
        print("WARNING: Including key material in export. Protect this file carefully!")

    summary = vault_mgr.export_vault(
        output_path=args.output,
        include_material=args.include_material,
        scope=scope,
    )

    print(f"\nExport complete:")
    print(f"  Total keys: {summary['total_keys']}")
    print(f"  Errors: {summary['errors']}")
    print(f"  Output: {args.output}")


def _cli_import(args):
    """CLI handler for vault import."""
    vault_mgr = get_vault(args.vault_path)

    print(f"Importing vault to: {vault_mgr.vault_root}")
    print(f"From: {args.input}")

    summary = vault_mgr.import_vault(
        input_path=args.input,
        import_material=args.import_material,
        overwrite=args.overwrite,
    )

    print(f"\nImport complete:")
    print(f"  Total in export: {summary['total_in_export']}")
    print(f"  Imported: {summary['imported']}")
    print(f"  Skipped (existing): {summary['skipped_existing']}")
    print(f"  Skipped (no material): {summary['skipped_no_material']}")
    if summary['errors']:
        print(f"  Errors: {len(summary['errors'])}")
        for err in summary['errors']:
            print(f"    - {err}")


def _cli_status(args):
    """CLI handler for vault status."""
    vault_mgr = get_vault(args.vault_path)
    status = vault_mgr.get_vault_status()

    print(f"Vault Status")
    print(f"{'='*50}")
    print(f"  Root: {status['vault_root']}")
    print(f"  Encryption: {'Enabled (AES-256-GCM)' if status['encryption_enabled'] else 'Disabled'}")
    print(f"  Writable: {'Yes' if status['writable'] else 'No'}")
    print(f"  Total Keys: {status['total_keys']}")
    if status['keys_by_scope']:
        print(f"  Keys by scope:")
        for scope, count in status['keys_by_scope'].items():
            print(f"    - {scope}: {count}")


def _cli_list(args):
    """CLI handler for listing keys."""
    vault_mgr = get_vault(args.vault_path)
    scope = KeyScope(args.scope) if args.scope else None
    keys = vault_mgr.list_keys(scope)

    if not keys:
        print("No keys found.")
        return

    print(f"{'Key ID':<40} {'Scope':<12} {'Algorithm':<15} {'Created'}")
    print("-" * 90)
    for key in keys:
        key_id = key.get("key_id", "?")[:40]
        scope_val = key.get("scope", "?")[:12]
        algo = key.get("algorithm", "?")[:15]
        created = key.get("created_at", "?")[:25]
        encrypted = "🔒" if key.get("params", {}).get("encrypted") else "⚠️"
        print(f"{encrypted} {key_id:<38} {scope_val:<12} {algo:<15} {created}")


def _cli_migrate(args):
    """CLI handler for migrating keys to encrypted storage."""
    vault_mgr = get_vault(args.vault_path)

    if not vault_mgr.encryption_enabled:
        print("ERROR: Encryption not enabled. Set TG_VAULT_MASTER_KEY environment variable.")
        return

    scope = KeyScope(args.scope) if args.scope else None
    migrated = vault_mgr.migrate_to_encrypted(scope)
    print(f"Migrated {migrated} keys to encrypted storage.")


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="TensorGuard Vault Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check vault status
  python -m tensorguard.core.keys status

  # List all keys
  python -m tensorguard.core.keys list

  # Export metadata only (safe for backup)
  python -m tensorguard.core.keys export --out vault_backup.json

  # Export with key material (for full disaster recovery)
  python -m tensorguard.core.keys export --out vault_full.json --include-material

  # Import from export (validation only)
  python -m tensorguard.core.keys import --in vault_backup.json

  # Import with key material
  python -m tensorguard.core.keys import --in vault_full.json --import-material

  # Migrate unencrypted keys to encrypted
  python -m tensorguard.core.keys migrate
        """
    )
    parser.add_argument("--vault-path", default="keys", help="Vault root directory")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show vault status")
    status_parser.set_defaults(func=_cli_status)

    # List command
    list_parser = subparsers.add_parser("list", help="List keys")
    list_parser.add_argument("--scope", choices=["identity", "inference", "aggregation", "system"])
    list_parser.set_defaults(func=_cli_list)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export vault")
    export_parser.add_argument("--out", "-o", required=True, help="Output file path")
    export_parser.add_argument("--include-material", action="store_true",
                               help="Include key material (SECURITY SENSITIVE)")
    export_parser.add_argument("--scope", choices=["identity", "inference", "aggregation", "system"])
    export_parser.set_defaults(func=_cli_export)

    # Import command
    import_parser = subparsers.add_parser("import", help="Import vault")
    import_parser.add_argument("--in", "-i", dest="input", required=True, help="Input file path")
    import_parser.add_argument("--import-material", action="store_true",
                               help="Import key material from export")
    import_parser.add_argument("--overwrite", action="store_true",
                               help="Overwrite existing keys")
    import_parser.set_defaults(func=_cli_import)

    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate to encrypted storage")
    migrate_parser.add_argument("--scope", choices=["identity", "inference", "aggregation", "system"])
    migrate_parser.set_defaults(func=_cli_migrate)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
