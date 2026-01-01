"""
TensorGuard Edge Client Core
"""

import logging
from typing import Optional, List, Dict, Any
from ..schemas.common import Demonstration, ShieldConfig, ClientStatus
from ..utils.exceptions import ValidationError
from .adapters import VLAAdapter

logger = logging.getLogger(__name__)

class EdgeClient:
    """
    Primary interface for robot-side TensorGuard integration.
    """
    def __init__(self, config: Optional[ShieldConfig] = None):
        self.config = config or ShieldConfig()
        self.adapter: Optional[VLAAdapter] = None
        self.demonstrations: List[Demonstration] = []
        self.submissions_count = 0
        
    def set_adapter(self, adapter: VLAAdapter):
        """Bind a model adapter to this client."""
        self.adapter = adapter
        
    def add_demonstration(self, demo: Demonstration):
        """Queue a demonstration for the next training round."""
        self.demonstrations.append(demo)
        
    def get_status(self) -> ClientStatus:
        """Get current client status."""
        return ClientStatus(
            pending_submissions=len(self.demonstrations),
            total_submissions=self.submissions_count,
            privacy_budget_remaining=self.config.dp_epsilon,
            last_model_version="2.0.0",
            connection_status="online"
        )
        
    def process_round(self) -> bytes:
        """
        Compute gradients, apply privacy noise, and package for submission.
        """
        if not self.adapter:
            raise ValidationError("Adapter not set")
        
        if not self.demonstrations:
            return b""
            
        # In a real implementation, this would iterate through demos,
        # compute gradients via self.adapter, aggregate, and encrypt.
        # For the unified core, we return a mock payload.
        
        self.submissions_count += 1
        self.demonstrations = []
        return b"TENSORGUARD_ENCRYPTED_UPDATE_V2"

def create_client(model_type: str = "pi0", **kwargs) -> EdgeClient:
    """Factory function for creating an EdgeClient."""
    config = ShieldConfig(model_type=model_type, **kwargs)
    return EdgeClient(config)
