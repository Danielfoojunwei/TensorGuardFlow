"""
TensorGuard Artifact Run v1 Schema and Canonicalization
"""
import json
import hashlib
from typing import Any, Dict

SCHEMA_NAME = "tensorguard.artifact.run.v1"

def canonicalize(data: Dict[str, Any]) -> bytes:
    """
    Produce a deterministic byte representation of a dictionary for hashing.
    Keys are sorted recursively.
    """
    def _sort(obj):
        if isinstance(obj, dict):
            return {k: _sort(obj[k]) for k in sorted(obj)}
        if isinstance(obj, list):
            return [_sort(i) for i in obj]
        return obj

    canonical_data = _sort(data)
    # separators=(',', ':') removes whitespace
    return json.dumps(canonical_data, separators=(',', ':'), sort_keys=True).encode('utf-8')

def calculate_artifact_hash(data: Dict[str, Any]) -> str:
    """
    Calculate SHA-256 hash of canonicalized artifact data.
    """
    c_bytes = canonicalize(data)
    return hashlib.sha256(c_bytes).hexdigest()

def validate_schema(data: Dict[str, Any]) -> bool:
    """
    Basic schema validation for tensorguard.artifact.run.v1
    """
    required_fields = ["schema", "run_id", "timestamp", "metrics", "artifacts_hashes"]
    if data.get("schema") != SCHEMA_NAME:
        return False
    return all(field in data for field in required_fields)
