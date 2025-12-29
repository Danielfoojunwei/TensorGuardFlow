"""
MOAI Model Exporter
Converts training checkpoints into FHE-servable ModelPacks.
"""

import json
import numpy as np
import pickle
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..core.adapters import FHEExportAdapter
from ..utils.logging import get_logger
from .modelpack import ModelPack, ModelPackMetadata
from .moai_config import MoaiConfig

logger = get_logger(__name__)

class MoaiExporter:
    """
    Handles the pipeline of:
    1. Loading a trained model checkpoint
    2. Extracting specific submodules (FHEExportAdapter)
    3. Packing/Quantizing per MOAI config
    4. Serializing to ModelPack
    """
    
    def __init__(self, config: MoaiConfig):
        self.config = config
        
    def export(self, 
               model_path: str, 
               model_id: str,
               target_modules: List[str],
               git_commit: str = "unknown") -> ModelPack:
        """
        Export a ModelPack from a checkpoint.
        """
        logger.info(f"Starting MOAI export for {model_id} targeting {target_modules}")
        
        # 1. Use Adapter to extract raw weights
        adapter = FHEExportAdapter(model_path, target_modules)
        
        # Simulating loading state_dict from path
        # In prod, this would be torch.load(model_path)
        # Here we generate mock weights matching the target modules
        mock_state_dict = {}
        for mod in target_modules:
            # Create a mock weight matrix (e.g. 128x64)
            mock_state_dict[f"{mod}.weight"] = np.random.randn(128, 64).astype(np.float32)
            mock_state_dict[f"{mod}.bias"] = np.random.randn(128).astype(np.float32)
            
        extracted_weights = adapter.extract_submodules(mock_state_dict)
        
        # 2. Quantization & Packing (Mocked)
        # In prod, we'd convert float32 -> int8 -> poly polynomials
        packed_weights = {}
        for k, v in extracted_weights.items():
            # For mock, we just pickle the numpy array
            # In real MOAI, this is where the layout transformation happens
            packed_weights[k] = pickle.dumps(v)
            
        # 3. Create Metadata
        meta = ModelPackMetadata(
            model_id=model_id,
            version="1.0.0",
            base_model="pi0",
            target_modules=target_modules,
            created_at=datetime.utcnow().isoformat(),
            git_commit_hash=git_commit,
            config=self.config.__dict__.copy() if hasattr(self.config, '__dict__') else {}
        )
        
        # 4. Assemble Package
        pack = ModelPack(
            meta=meta,
            weights=packed_weights,
            tokenizer_config={"vocab_size": 32000} # Mock
        )
        
        logger.info(f"Exported ModelPack: {model_id} with {len(packed_weights)} tensors")
        return pack

def export_moai_modelpack(model_path: str, output_path: str, target_modules: List[str] = None):
    """CLI Entrypoint for export."""
    config = MoaiConfig() # Default config
    exporter = MoaiExporter(config)
    
    targets = target_modules or ["policy_head"]
    pack = exporter.export(model_path, "moai-model-v1", targets)
    
    with open(output_path, 'wb') as f:
        f.write(pack.serialize())
    
    logger.info(f"Saved ModelPack to {output_path}")
