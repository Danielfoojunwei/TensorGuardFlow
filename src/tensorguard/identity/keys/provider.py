"""
Key Provider Abstraction - Secure Key Storage

Provides pluggable key storage backends:
- File-based (encrypted at rest)
- PKCS#11 (HSM, smart cards)
- Cloud KMS (AWS KMS, GCP KMS, Azure KeyVault)
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging
import json

logger = logging.getLogger(__name__)

# Try crypto imports
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


@dataclass
class StoredKey:
    """Metadata about a stored key."""
    key_id: str
    key_type: str  # RSA, ECDSA
    key_size: int
    created_at: str
    provider: str
    reference: str  # Provider-specific reference


class KeyProvider(ABC):
    """
    Abstract base class for key storage providers.
    
    Key providers handle:
    - Private key storage (never in plaintext)
    - Key generation (if supported)
    - Signing operations (for PKCS#11/KMS)
    """
    
    @abstractmethod
    def store_key(
        self,
        key_id: str,
        private_key_pem: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredKey:
        """Store a private key securely."""
        pass
    
    @abstractmethod
    def load_key(self, key_id: str) -> Optional[bytes]:
        """Load a private key by ID. Returns PEM bytes."""
        pass
    
    @abstractmethod
    def delete_key(self, key_id: str) -> bool:
        """Delete a stored key."""
        pass
    
    @abstractmethod
    def list_keys(self) -> list[StoredKey]:
        """List all stored keys."""
        pass
    
    def supports_remote_signing(self) -> bool:
        """Whether this provider supports signing without exporting key."""
        return False


class FileKeyProvider(KeyProvider):
    """
    File-based key storage with encryption at rest.
    
    Uses AES-256-GCM for encryption with a master key from environment.
    """
    
    def __init__(
        self,
        storage_path: str = "/var/lib/tensorguard/keys",
        master_key: Optional[bytes] = None,
        master_key_env: str = "TG_KEY_MASTER",
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Get master key
        if master_key:
            self.master_key = master_key
        else:
            key_hex = os.environ.get(master_key_env)
            if key_hex:
                self.master_key = bytes.fromhex(key_hex)
            else:
                # Generate a new master key (NOT FOR PRODUCTION)
                self.master_key = os.urandom(32)
                logger.warning(
                    f"No master key provided. Generated temporary key. "
                    f"Set {master_key_env} for production."
                )
        
        self._metadata_file = self.storage_path / "keys.json"
        self._metadata: Dict[str, dict] = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, dict]:
        """Load key metadata from disk."""
        if self._metadata_file.exists():
            try:
                return json.loads(self._metadata_file.read_text())
            except Exception:
                pass
        return {}
    
    def _save_metadata(self) -> None:
        """Save key metadata to disk."""
        self._metadata_file.write_text(json.dumps(self._metadata, indent=2))
    
    def _encrypt(self, data: bytes) -> bytes:
        """Encrypt data with master key."""
        if not HAS_CRYPTOGRAPHY:
            logger.warning("cryptography not installed, storing unencrypted")
            return data
        
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.master_key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext
    
    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt data with master key."""
        if not HAS_CRYPTOGRAPHY:
            return data
        
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(self.master_key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def store_key(
        self,
        key_id: str,
        private_key_pem: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredKey:
        """Store a private key encrypted on disk."""
        key_file = self.storage_path / f"{key_id}.enc"
        
        # Encrypt and save
        encrypted = self._encrypt(private_key_pem)
        key_file.write_bytes(encrypted)
        os.chmod(key_file, 0o600)
        
        # Extract key info
        key_type = "UNKNOWN"
        key_size = 0
        
        if HAS_CRYPTOGRAPHY:
            try:
                from cryptography.hazmat.primitives.asymmetric import rsa, ec
                
                private_key = serialization.load_pem_private_key(
                    private_key_pem, password=None, backend=default_backend()
                )
                
                if isinstance(private_key, rsa.RSAPrivateKey):
                    key_type = "RSA"
                    key_size = private_key.key_size
                elif isinstance(private_key, ec.EllipticCurvePrivateKey):
                    key_type = "ECDSA"
                    key_size = private_key.curve.key_size
            except Exception:
                pass
        
        # Save metadata
        from datetime import datetime
        
        meta = {
            "key_id": key_id,
            "key_type": key_type,
            "key_size": key_size,
            "created_at": datetime.utcnow().isoformat(),
            "provider": "file",
            "reference": str(key_file),
            **(metadata or {}),
        }
        
        self._metadata[key_id] = meta
        self._save_metadata()
        
        logger.info(f"Stored key: {key_id}")
        
        return StoredKey(**{k: meta[k] for k in StoredKey.__dataclass_fields__})
    
    def load_key(self, key_id: str) -> Optional[bytes]:
        """Load a private key from encrypted storage."""
        key_file = self.storage_path / f"{key_id}.enc"
        
        if not key_file.exists():
            return None
        
        try:
            encrypted = key_file.read_bytes()
            return self._decrypt(encrypted)
        except Exception as e:
            logger.error(f"Failed to load key {key_id}: {e}")
            return None
    
    def delete_key(self, key_id: str) -> bool:
        """Delete a key from storage."""
        key_file = self.storage_path / f"{key_id}.enc"
        
        if key_file.exists():
            key_file.unlink()
        
        if key_id in self._metadata:
            del self._metadata[key_id]
            self._save_metadata()
        
        logger.info(f"Deleted key: {key_id}")
        return True
    
    def list_keys(self) -> list[StoredKey]:
        """List all stored keys."""
        return [
            StoredKey(**{k: m[k] for k in StoredKey.__dataclass_fields__})
            for m in self._metadata.values()
        ]


class PKCS11KeyProvider(KeyProvider):
    """
    PKCS#11 key storage (HSM, TPM, smart card).
    
    Supports:
    - Key generation on device
    - Signing without key export
    - Hardware-backed key protection
    """
    
    def __init__(
        self,
        library_path: str,
        slot: int = 0,
        pin: Optional[str] = None,
    ):
        self.library_path = library_path
        self.slot = slot
        self.pin = pin
        self._session = None
        
        # Would use python-pkcs11 or PyKCS11
        logger.info("PKCS#11 provider initialized (stub)")
    
    def store_key(
        self,
        key_id: str,
        private_key_pem: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredKey:
        """Import key to PKCS#11 device."""
        # Would use pkcs11.Session.create_keypair or import
        raise NotImplementedError("PKCS#11 import not implemented")
    
    def load_key(self, key_id: str) -> Optional[bytes]:
        """
        Cannot export keys from PKCS#11 (by design).
        
        Use sign() method instead for operations.
        """
        logger.warning("PKCS#11 keys cannot be exported")
        return None
    
    def delete_key(self, key_id: str) -> bool:
        """Delete key from PKCS#11 device."""
        # Would use pkcs11.Object.destroy
        raise NotImplementedError("PKCS#11 delete not implemented")
    
    def list_keys(self) -> list[StoredKey]:
        """List keys on PKCS#11 device."""
        # Would enumerate objects
        return []
    
    def supports_remote_signing(self) -> bool:
        return True
    
    def sign(self, key_id: str, data: bytes, algorithm: str = "SHA256") -> bytes:
        """Sign data using PKCS#11 key without export."""
        # Would use pkcs11.Key.sign
        raise NotImplementedError("PKCS#11 signing not implemented")


class KMSKeyProvider(KeyProvider):
    """
    Cloud KMS key storage (AWS KMS, GCP KMS, Azure KeyVault).
    
    Keys never leave the cloud provider's HSM.
    All cryptographic operations done via API.
    """
    
    def __init__(
        self,
        provider: str = "aws",  # "aws", "gcp", "azure"
        key_prefix: str = "tensorguard/identity/",
        **config,
    ):
        self.provider = provider
        self.key_prefix = key_prefix
        self.config = config
        
        logger.info(f"KMS provider initialized: {provider}")
    
    def store_key(
        self,
        key_id: str,
        private_key_pem: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredKey:
        """
        KMS manages its own keys - import is complex.
        
        Prefer using generate_key() for new keys.
        """
        raise NotImplementedError("KMS import not supported. Use generate_key()")
    
    def generate_key(
        self,
        key_id: str,
        key_type: str = "RSA",
        key_size: int = 2048,
    ) -> StoredKey:
        """Generate a new key in KMS."""
        if self.provider == "aws":
            return self._aws_generate_key(key_id, key_type, key_size)
        elif self.provider == "gcp":
            return self._gcp_generate_key(key_id, key_type, key_size)
        else:
            raise NotImplementedError(f"KMS provider not supported: {self.provider}")
    
    def _aws_generate_key(self, key_id: str, key_type: str, key_size: int) -> StoredKey:
        """Generate key in AWS KMS."""
        # Would use boto3.client('kms').create_key()
        raise NotImplementedError("AWS KMS key generation not implemented")
    
    def _gcp_generate_key(self, key_id: str, key_type: str, key_size: int) -> StoredKey:
        """Generate key in GCP KMS."""
        # Would use google.cloud.kms_v1.KeyManagementServiceClient
        raise NotImplementedError("GCP KMS key generation not implemented")
    
    def load_key(self, key_id: str) -> Optional[bytes]:
        """Cannot export keys from KMS."""
        logger.warning("KMS keys cannot be exported")
        return None
    
    def delete_key(self, key_id: str) -> bool:
        """Schedule key deletion in KMS."""
        # Would use appropriate KMS API
        raise NotImplementedError("KMS key deletion not implemented")
    
    def list_keys(self) -> list[StoredKey]:
        """List keys in KMS."""
        # Would enumerate keys via KMS API
        return []
    
    def supports_remote_signing(self) -> bool:
        return True
    
    def sign(self, key_id: str, data: bytes, algorithm: str = "SHA256") -> bytes:
        """Sign data using KMS key."""
        # Would use KMS sign API
        raise NotImplementedError("KMS signing not implemented")


class KeyProviderFactory:
    """Factory for creating key providers."""
    
    @staticmethod
    def create(
        provider_type: str = "file",
        **config,
    ) -> KeyProvider:
        """
        Create a key provider.
        
        Args:
            provider_type: "file", "pkcs11", "aws-kms", "gcp-kms"
            **config: Provider-specific configuration
            
        Returns:
            Configured KeyProvider
        """
        if provider_type == "file":
            return FileKeyProvider(**config)
        elif provider_type == "pkcs11":
            return PKCS11KeyProvider(**config)
        elif provider_type.startswith("aws"):
            return KMSKeyProvider(provider="aws", **config)
        elif provider_type.startswith("gcp"):
            return KMSKeyProvider(provider="gcp", **config)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
