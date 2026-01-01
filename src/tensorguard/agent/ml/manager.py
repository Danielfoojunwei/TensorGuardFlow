"""
ML Manager - Subsystem Controller for Federated Learning

Manages the TrainingWorker and integration with the Unified Config.
"""

import logging
import threading
import time
from typing import Optional
from ...schemas.unified_config import MLConfig

from .worker import TrainingWorker, WorkerConfig

logger = logging.getLogger(__name__)

class MLManager:
    """
    Subsystem controller for Machine Learning tasks.
    """
    def __init__(self, agent_config: 'AgentConfig', config_manager: 'ConfigManager'):
        self.config: MLConfig = agent_config.ml
        self.fleet_id = agent_config.fleet_id
        
        self.worker: Optional[TrainingWorker] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def configure(self, new_config: MLConfig):
        """Reconfigure ML subsystem."""
        logger.info("Reconfiguring ML Manager")
        self.config = new_config
        self._init_worker()

    def _init_worker(self):
        """Initialize the TrainingWorker."""
        worker_config = WorkerConfig(
            model_type=self.config.model_type,
            max_gradient_norm=self.config.max_gradient_norm,
            dp_epsilon=self.config.dp_epsilon,
            sparsity=self.config.sparsity,
            compression_ratio=self.config.compression_ratio
        )
        self.worker = TrainingWorker(worker_config, cid=self.fleet_id)
        
        # Determine adapter based on model_type (stub)
        # from tensorguard.core.adapters import Pi0Adapter
        # self.worker.set_adapter(Pi0Adapter())

    def start(self):
        """Start the training loop (e.g., Flower client)."""
        if not self.config.enabled:
            return
            
        self._init_worker()
        self.running = True
        
        self._thread = threading.Thread(target=self._run_flower, daemon=True)
        self._thread.start()
        logger.info("ML Manager started")

    def stop(self):
        """Stop training."""
        self.running = False
        # Flower client is blocking, so we can't easily stop it from outside
        # unless we terminate the process or it has a timeout.
        if self._thread:
            # self._thread.join(timeout=2.0) # Don't block on join as flwr might hang
            pass
        logger.info("ML Manager stopped")

    def _run_flower(self):
        """Run the Flower client loop."""
        if not self.worker:
            return
            
        server_address = self.config.aggregator_url.replace("http://", "").replace("https://", "") if hasattr(self.config, 'aggregator_url') else "127.0.0.1:8080"
        
        while self.running:
            try:
                import flwr as fl
                # Run if flwr is installed
                if server_address:
                     logger.info(f"Connecting to aggregator at {server_address}")
                     fl.client.start_numpy_client(server_address=server_address, client=self.worker)
            except ImportError:
                logger.warning("Flower not installed, skipping FL loop")
                break
            except Exception as e:
                logger.error(f"Flower client error: {e}")
            
            # Retry interval
            time.sleep(10)

    def ingest_demonstration(self, demo_data: dict):
        """API for ingestion of local demonstrations."""
        if self.worker:
            self.worker.add_demonstration(demo_data)
            logger.info("Demonstration ingested")
