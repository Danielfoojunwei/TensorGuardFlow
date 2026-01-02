
import json
import os
import uuid
from typing import IO
from .canonical import canonical_bytes

class EvidenceStore:
    def __init__(self, output_dir: str = "artifacts/evidence"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def save_event(self, event_dict: dict) -> str:
        """Write signed event to disk."""
        # Use simple naming: timestamp_type_id.tge.json
        ts = int(event_dict.get("timestamp", 0))
        etype = event_dict.get("event_type", "UNKNOWN")
        eid = event_dict.get("event_id", "unknown")
        
        filename = f"{ts}_{etype}_{eid}.tge.json"
        path = os.path.join(self.output_dir, filename)
        
        # Serialize canonically using JSON 
        data = canonical_bytes(event_dict)
        
        with open(path, "wb") as f:
            f.write(data)
            
        return path
    
    def load_event(self, path: str) -> dict:
        with open(path, "rb") as f:
            return json.load(f)

# Global singleton helper
_store = None

def get_store() -> EvidenceStore:
    global _store
    if _store is None:
        _store = EvidenceStore()
    return _store
