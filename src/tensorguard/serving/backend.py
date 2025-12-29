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

class TenSEALBackend(MoaiBackend):
    """
    Real FHE backend using TenSEAL (CKKS).
    """
    
    def __init__(self):
        self.active_model: ModelPack = None
        self.unpacked_weights: Dict[str, np.ndarray] = {}
        
    def load_model(self, model_pack: ModelPack):
        self.active_model = model_pack
        # Unpack weights (these are plaintext weights for hybrid homomorphic inference)
        # In this scheme: Encrypted Input x Plaintext Weights = Encrypted Output
        self.unpacked_weights = {}
        for k, v in model_pack.weights.items():
            self.unpacked_weights[k] = pickle.loads(v)
            
        logger.info(f"TenSEALBackend loaded model {model_pack.meta.model_id}")

    def infer(self, ciphertext: bytes, eval_keys: bytes) -> bytes:
        import tenseal as ts
        
        if not self.active_model:
            raise RuntimeError("No model loaded")
            
        try:
            # 1. Load Context (Server Side - Public Context Only)
            ctx = ts.context_from(eval_keys)
            
            # 2. Deserialize Encrypted Input
            enc_vec = ts.ckks_vector_from(ctx, ciphertext)
            
            # 3. Homomorphic Linear Layer: x @ W + b
            weights = list(self.unpacked_weights.values())
            if len(weights) >= 2:
                W = weights[0] # Expecting (Out, In) from PyTorch state_dict convention
                b = weights[1] # Expecting (Out,)
                
                # Input vector shape matches In features?
                # TenSEAL CKKS vector is essentially 1D.
                # If we do x @ W.T (standard Linear), we need W.T to be (In, Out)
                
                # Convert to numpy if not already
                if not isinstance(W, np.ndarray): W = np.array(W)
                if not isinstance(b, np.ndarray): b = np.array(b)
                
                # Transpose for x @ W_transposed
                W_t = W.T
                
                # TenSEAL expects pure Python lists for plain tensors
                W_list = W_t.tolist()
                b_list = b.tolist()
                
                # Perform MatMul: (1, In) @ (In, Out) -> (1, Out)
                res = enc_vec.matmul(W_list)
                res.add(b_list)
                
            else:
                res = enc_vec
                
            # 4. Return Encrypted Result
            return res.serialize()
                
            # 4. Return Encrypted Result
            return res.serialize()
            
        except Exception as e:
            logger.error(f"FHE Inference Failed: {e}")
            raise ValueError(f"FHE Error: {e}")
class NativeBackend(MoaiBackend):
    """Placeholder for C++ MOAI runtime."""
    def load_model(self, model_pack: ModelPack):
        raise NotImplementedError("Native MOAI runtime not available inside python-only environment.")
        
    def infer(self, ciphertext: bytes, eval_keys: bytes) -> bytes:
        raise NotImplementedError("Native MOAI runtime not available.")
