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
