import cbor2
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

@dataclass
class PayloadDescriptor:
    payload_id: str
    logical_type: str # e.g. 'adapter', 'config'
    filename: str
    enc_hash: str     # SHA-256 of encrypted file
    plaintext_hash: str # SHA-256 of original file
    cipher: str = "AES-256-GCM"

@dataclass
class EvidenceDescriptor:
    type: str # 'json', 'html'
    filename: str
    hash: str

@dataclass
class PackageManifest:
    package_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    producer_id: str = "tensorguard-producer-1"
    producer_pubkey_ed25519: str = "" # Base64
    base_model_ids: List[str] = field(default_factory=list)
    policy_id: str = ""
    policy_version: str = ""
    policy_hash: str = ""
    payloads: List[PayloadDescriptor] = field(default_factory=list)
    evidence: List[EvidenceDescriptor] = field(default_factory=list)
    file_inventory: Dict[str, str] = field(default_factory=dict) # path -> hash

    def to_canonical_cbor(self) -> bytes:
        # Recursive sorting of dictionaries for canonical representation
        data = self._sort_dict(asdict(self))
        return cbor2.dumps(data)

    def _sort_dict(self, d):
        if isinstance(d, dict):
            return {k: self._sort_dict(v) for k, v in sorted(d.items())}
        if isinstance(d, list):
            return [self._sort_dict(i) for i in d]
        return d

    @classmethod
    def from_cbor(cls, data: bytes) -> 'PackageManifest':
        decoded = cbor2.loads(data)
        # Reconstruct from dict
        payloads = [PayloadDescriptor(**p) for p in decoded.pop('payloads', [])]
        evidence = [EvidenceDescriptor(**e) for e in decoded.pop('evidence', [])]
        return cls(payloads=payloads, evidence=evidence, **decoded)
