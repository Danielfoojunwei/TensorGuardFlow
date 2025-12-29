"""
MOAI Inference Backend
"""

import abc
import pickle
import numpy as np
import time
from typing import Dict, Any, List

from ..moai.modelpack import ModelPack
from ..utils.logging import get_logger

logger = get_logger(__name__)

class MoaiBackend(abc.ABC):
    """Abstract interface for FHE inference backends."""
    
    @abc.abstractmethod
    def load_model(self, model_pack: ModelPack):
        """Load a ModelPack into the runtime."""
        pass
        
    @abc.abstractmethod
    def infer(self, ciphertext: bytes, eval_keys: bytes) -> bytes:
        """Run FHE inference."""
        pass

class MockBackend(MoaiBackend):
    """
    Simulation backend that performs "encrypted" inference using
    plain numpy operations on picked data.
    """
    
    def __init__(self):
        self.active_model: ModelPack = None
        self.unpacked_weights: Dict[str, np.ndarray] = {}
        
    def load_model(self, model_pack: ModelPack):
        self.active_model = model_pack
        # Unpack mock weights
        self.unpacked_weights = {}
        for k, v in model_pack.weights.items():
            self.unpacked_weights[k] = pickle.loads(v)
            
        logger.info(f"MockBackend loaded model {model_pack.meta.model_id}")

    def infer(self, ciphertext: bytes, eval_keys: bytes) -> bytes:
        if not self.active_model:
            raise RuntimeError("No model loaded")
            
        # Simulate Processing Delay (FHE is slow)
        time.sleep(0.05) 
        
        # 1. "Decrypt" input (deserialize)
        try:
            input_payload = pickle.loads(ciphertext)
            input_vec = np.array(input_payload["data"])
        except Exception:
            raise ValueError("Invalid mock ciphertext")
            
        # 2. Run Inference (Mock Linear Layer: x @ W + b)
        # We just grab the first weight/bias we find for demo
        # In reality this would route through the expert graph
        weights = list(self.unpacked_weights.values())
        if len(weights) >= 2:
            W = weights[0] # Weight
            b = weights[1] # Bias
            
            # Simple dimensionality fix if shapes mismatch for demo
            if input_vec.shape[-1] != W.shape[0]:
                 # Projection to match dimensions for mock
                 W = np.random.randn(input_vec.shape[-1], 10)
                 b = np.random.randn(10)
            
            result = input_vec @ W + b
        else:
            # Fallback
            result = input_vec 
            
        # 3. "Encrypt" output
        output_payload = {
            "data": result.tolist(),
            "is_encrypted": True,
            "provenance": "MockBackend"
        }
        
        return pickle.dumps(output_payload)

class NativeBackend(MoaiBackend):
    """Placeholder for C++ MOAI runtime."""
    def load_model(self, model_pack: ModelPack):
        raise NotImplementedError("Native MOAI runtime not available inside python-only environment.")
        
    def infer(self, ciphertext: bytes, eval_keys: bytes) -> bytes:
        raise NotImplementedError("Native MOAI runtime not available.")
