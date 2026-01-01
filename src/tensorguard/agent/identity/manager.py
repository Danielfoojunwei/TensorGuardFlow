"""
Identity Manager - Subsystem Controller

Manages the lifecycle of identity services within the Unified Agent.
Wraps the Scanner, CSR Generator, and communication logic.
"""

import logging
import threading
import time
from typing import Optional, List
from ...schemas.unified_config import IdentityConfig

from .scanner import CertificateScanner
from .csr_generator import CSRGenerator
from .deployers import DeployerFactory

logger = logging.getLogger(__name__)

class IdentityManager:
    """
    Subsystem controller for Machine Identity Guard.
    """
    def __init__(self, agent_config: 'AgentConfig', config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.config: IdentityConfig = agent_config.identity
        self.fleet_id = agent_config.fleet_id
        self.api_key = agent_config.api_key
        
        self.scanner = CertificateScanner()
        self.csr_generator = CSRGenerator(key_storage_path=self.config.key_storage_path)
        
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def configure(self, new_config: IdentityConfig):
        """Update configuration on the fly."""
        logger.info("Reconfiguring Identity Manager")
        self.config = new_config
        # Restart loop if needed

    def start(self):
        """Start background tasks."""
        if not self.config.enabled:
            return
            
        logger.info("IdentityManager starting...")
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop background tasks."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run_loop(self):
        """Main identity loop."""
        while self.running:
            try:
                # 1. Periodic Scan
                self.run_scan()
                
                # 2. Check for Renewals (stub)
                # self.check_renewals()
                
            except Exception as e:
                logger.error(f"Identity loop error: {e}")
            
            # Sleep interval
            for _ in range(self.config.scan_interval_seconds):
                if not self.running:
                    break
                time.sleep(1)

    def run_scan(self) -> List[dict]:
        """Execute a certificate scan."""
        logger.info("Executing periodic certificate scan")
        certs = self.scanner.scan_all(
            include_kubernetes=self.config.scan_kubernetes,
            include_nginx=self.config.scan_nginx,
            include_envoy=self.config.scan_envoy,
            include_filesystem=self.config.scan_filesystem,
        )
        
        # Report results (stub - would call Control Plane via config_manager helper or specific client)
        self._report_certificates(certs)
        return certs

    def _report_certificates(self, certs: List):
        """Send certificates to control plane."""
        # This interaction logic needs to be centralized or passed in
        pass
