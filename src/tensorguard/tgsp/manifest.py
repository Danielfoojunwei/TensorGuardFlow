
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import time
from ..evidence.canonical import canonical_bytes
from ..evidence.store import get_store
import hashlib

class TGSPManifest(BaseModel):
    tgsp_version: str = "0.2"
    package_id: str
    model_name: str
    model_version: str
    author_id: str
    created_at: float = Field(default_factory=time.time)
    
    payload_hash: str # SHA-256 of encrypted payload (or compressed if v0.1)
    
    content_index: List[Dict[str, str]] = [] # [{path, sha256}]
    
    policy_constraints: Dict[str, Any] = {}
    build_info: Dict[str, str] = {}
    
    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.model_dump())
        
    def get_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
