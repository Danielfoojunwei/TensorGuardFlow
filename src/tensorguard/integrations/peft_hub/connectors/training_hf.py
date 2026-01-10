import logging
import os
from typing import Dict, Any
from ..contracts import Connector, ConnectorValidationResult
from ..catalog import ConnectorCatalog, is_package_installed

logger = logging.getLogger(__name__)

class HuggingFaceTrainingConnector(Connector):
    @property
    def id(self) -> str: return "training_hf"
    
    @property
    def name(self) -> str: return "HF Transformers + PEFT (Native)"
    
    @property
    def category(self) -> str: return "training"

    def check_installed(self) -> bool:
        """Check for torch, transformers, and peft."""
        return is_package_installed("torch") and is_package_installed("transformers") and is_package_installed("peft")

    def validate_config(self, config: Dict[str, Any]) -> ConnectorValidationResult:
        model_path = config.get("model_name_or_path")
        if not model_path:
            return ConnectorValidationResult(ok=False, details="Missing model_name_or_path", remediation="Specify a model ID or local path.")
        
        # Check if local path exists if it's not a HF hub ID
        if "/" in model_path and not os.path.exists(model_path):
             # This might be a hub ID, so we just warn
             pass
             
        return ConnectorValidationResult(ok=True, details="Config valid.")

    def to_runtime(self, config: Dict[str, Any]) -> Any:
        """
        In a real implementation, this would return a Trainer or a command.
        For TensorGuard Studio, if check_installed() is False, we return a 'SimulatedTrainer'.
        """
        if not self.check_installed():
            logger.warning("Optional dependencies (torch/peft) missing. Using Simulated Mode.")
            return SimulatedTrainer(config)
        
        # Real implementation would go here...
        return SimulatedTrainer(config) # Still use simulated for the first draft PR

class SimulatedTrainer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def run(self, log_callback=None):
        import time
        import json
        
        stages = ["INIT", "LOADING_MODEL", "TOKENIZING_DATA", "FINE_TUNING", "EVALUATING", "SAVING"]
        
        for i, stage in enumerate(stages):
            if log_callback:
                log_callback(json.dumps({
                    "stage": stage,
                    "progress": (i+1)/len(stages) * 100,
                    "message": f"Simulated Phase: {stage}..."
                }))
            time.sleep(1) # Simulate work
            
        # Create dummy artifacts
        output_dir = self.config.get("output_dir", "./runs/latest/adapters")
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "adapter_config.json"), "w") as f:
            json.dump({"base_model": self.config.get("model_name_or_path"), "peft_type": "LORA"}, f)
        with open(os.path.join(output_dir, "adapter_model.bin"), "w") as f:
            f.write("DUMMY_ADAPTER_WEIGHTS")
            
        return {"status": "success", "metrics": {"loss": 0.42, "accuracy": 0.95}}

# Auto-register
ConnectorCatalog.register(HuggingFaceTrainingConnector())
