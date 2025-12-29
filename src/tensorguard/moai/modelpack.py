"""
MOAI Model Packaging
Defines the schema for exporting FHE-servable submodules.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import hashlib

from .moai_config import MoaiConfig

@dataclass
class ModelPackMetadata:
    """Metadata for an exported MOAI model package."""
    model_id: str
    version: str
    base_model: str # e.g. "pi0", "openvla"
    target_modules: List[str] # e.g. ["policy_head", "visual_router"]
    created_at: str
    git_commit_hash: str
    config: Dict[str, Any]

@dataclass
class ModelPack:
    """
    Container for a FHE-optimized model export.
    Contains weights, config, and verification hashes.
    """
    meta: ModelPackMetadata
    weights: Dict[str, bytes] # Serialized weights (could be raw numpy or pre-packed)
    tokenizer_config: Optional[Dict[str, Any]] = None
    
    def calculate_hash(self) -> str:
        """Calculate integrity hash of the package."""
        data = {
            "meta": asdict(self.meta),
            "weights_keys": sorted(self.weights.keys()),
            # hashing content would be better but expensive for large weights
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    
    def serialize(self) -> bytes:
        """Serialize mostly for storage/transfer."""
        import pickle
        return pickle.dumps(self)
    
    @classmethod
    def load(cls, path: str) -> 'ModelPack':
        import pickle
        with open(path, 'rb') as f:
            return pickle.load(f)
