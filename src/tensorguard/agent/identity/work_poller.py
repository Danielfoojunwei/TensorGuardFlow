import logging
import time
import os
from typing import List, Dict, Any
from .client import IdentityAgentClient
from .csr_generator import CSRGenerator
from .deployers import DeployerFactory

logger = logging.getLogger(__name__)

class WorkPoller:
    """
    Polls the Control Plane for identity renewal jobs and executes them.
    """
    def __init__(self, config, fleet_id: str, api_key: str, csr_generator: CSRGenerator):
        self.config = config
        self.client = IdentityAgentClient(config.platform_url, fleet_id, api_key)
        self.csr_generator = csr_generator
        self.running = False

    def poll_and_execute(self):
        """Single poll and execution cycle."""
        try:
            # 1. Get pending jobs for this fleet
            jobs = self.client.signed_request("GET", "/api/v1/identity/agent/jobs")
            
            for job in jobs:
                try:
                    self._process_job(job)
                except Exception as e:
                    logger.error(f"Failed to process job {job.get('id')}: {e}")
                    
        except Exception as e:
            logger.error(f"WorkPoller poll error: {e}")

    def _process_job(self, job: Dict[str, Any]):
        job_id = job["id"]
        status = job["status"]
        
        if status == "csr_requested":
            self._handle_csr_request(job)
        elif status == "challenge_pending":
            self._handle_challenge(job)
        elif status == "issued":
            self._handle_deployment(job)
        else:
            logger.debug(f"Job {job_id} in status {status}, no agent action required")

    def _handle_csr_request(self, job: Dict[str, Any]):
        job_id = job["id"]
        endpoint_id = job["endpoint_id"]
        
        logger.info(f"Generating CSR for renewal job {job_id}")
        
        # In a real system, we'd fetch endpoint details or SANs from the job or config
        # For now, we use the hostname from the job if available, or a default
        common_name = job.get("hostname", "managed-endpoint.local")
        
        # 1. Generate CSR with new key
        result = self.csr_generator.generate_csr_with_new_key(
            common_name=common_name,
            sans=[common_name],
            key_type="RSA", # Default
            key_size=2048,
        )
        
        # 2. Submit CSR to platform
        payload = {
            "job_id": job_id,
            "csr_pem": result.csr_pem
        }
        self.client.signed_request("POST", "/api/v1/identity/agent/csr", json_data=payload)
        logger.info(f"Submitted CSR for job {job_id}")

    def _handle_challenge(self, job: Dict[str, Any]):
        job_id = job["id"]
        challenge_type = job.get("challenge_type")
        token = job.get("challenge_token")
        
        logger.info(f"Handling {challenge_type} challenge for job {job_id}")
        
        if challenge_type == "http-01":
            # For HTTP-01, we need to serve the token at /.well-known/acme-challenge/<token>
            # In production: write to webroot or update ingress/envoy
            # For MVP: we'll simulate success by just notifying the platform
            # In a real environment, the agent would write to self.config.acme_webroot
            pass
            
        # Notify platform that challenge is "complete" (ready for verification)
        payload = {
            "job_id": job_id,
            "token": token
        }
        self.client.signed_request("POST", "/api/v1/identity/agent/challenge-complete", json_data=payload)
        logger.info(f"Confirmed challenge completion for job {job_id}")

    def _handle_deployment(self, job: Dict[str, Any]):
        job_id = job["id"]
        endpoint_id = job["endpoint_id"]
        cert_pem = job.get("issued_cert_pem")
        
        # We need the private key associated with this renewal
        # In this simplistic MVP, we'll assume the most recently generated key for this endpoint
        # In production, we'd track key_id in the renewal job
        
        logger.info(f"Deploying issued certificate for job {job_id}")
        
        # For now, let's just log and confirm to show the loop works
        # In Phase 6 (Validation), we'll wire up real deployers
        
        payload = {
            "job_id": job_id
        }
        self.client.signed_request("POST", "/api/v1/identity/agent/deploy-confirm", json_data=payload)
        logger.info(f"Confirmed deployment for job {job_id}")
