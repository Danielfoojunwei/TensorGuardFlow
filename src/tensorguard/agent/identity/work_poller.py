import logging
import time
import os
import json
from pathlib import Path
from typing import List, Dict, Any
from .client import IdentityAgentClient
from .csr_generator import CSRGenerator
from .deployers import DeployerFactory
from ...utils.production_gates import ProductionGateError

logger = logging.getLogger(__name__)

class WorkPoller:
    """
    Polls the Control Plane for identity renewal jobs and executes them.
    """
    def __init__(self, config, fleet_id: str, api_key: str, csr_generator: CSRGenerator):
        self.config = config
        self.client = IdentityAgentClient(config.control_plane_url, fleet_id, api_key)
        self.csr_generator = csr_generator
        self.running = False
        self._job_key_map_path = Path(config.data_dir) / "identity" / "renewal_job_keys.json"
        self._job_key_ids = self._load_job_key_map()

    def _load_job_key_map(self) -> Dict[str, str]:
        try:
            if self._job_key_map_path.exists():
                return json.loads(self._job_key_map_path.read_text())
        except Exception as e:
            logger.warning(f"Failed to load job key map: {e}")
        return {}

    def _save_job_key_map(self) -> None:
        try:
            self._job_key_map_path.parent.mkdir(parents=True, exist_ok=True)
            self._job_key_map_path.write_text(json.dumps(self._job_key_ids))
        except Exception as e:
            logger.error(f"Failed to persist job key map: {e}")

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

        self._job_key_ids[job_id] = result.key_id
        self._save_job_key_map()
        
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
        key_authorization = job.get("challenge_key_authorization")
        
        logger.info(f"Handling {challenge_type} challenge for job {job_id}")
        
        if challenge_type == "http-01":
            webroot = self.config.identity.acme_webroot
            if not webroot or not token or not key_authorization:
                raise ProductionGateError(
                    gate_name="ACME_HTTP01",
                    message="HTTP-01 challenge cannot be completed without acme_webroot, token, and key_authorization.",
                    remediation=(
                        "Configure identity.acme_webroot on the agent and ensure the control plane "
                        "provides ACME key authorization for the challenge."
                    ),
                )

            challenge_dir = Path(webroot) / ".well-known" / "acme-challenge"
            challenge_dir.mkdir(parents=True, exist_ok=True)
            token_path = challenge_dir / token
            token_path.write_text(key_authorization)
            logger.info(f"Wrote ACME HTTP-01 challenge token to {token_path}")
        elif challenge_type == "dns-01":
            raise ProductionGateError(
                gate_name="ACME_DNS01",
                message="DNS-01 challenge handling is not configured on the agent.",
                remediation="Provide a DNS automation hook for DNS-01 or switch to HTTP-01 with acme_webroot.",
            )
        else:
            raise ProductionGateError(
                gate_name="ACME_CHALLENGE_UNSUPPORTED",
                message=f"Unsupported ACME challenge type: {challenge_type}",
                remediation="Use a supported challenge type (http-01 or dns-01).",
            )
            
        # Notify platform that challenge is "complete" (ready for verification)
        payload = {
            "job_id": job_id,
            "token": token
        }
        self.client.signed_request("POST", "/api/v1/identity/agent/challenge-complete", json_data=payload)
        logger.info(f"Confirmed challenge completion for job {job_id}")

    def _handle_deployment(self, job: Dict[str, Any]):
        job_id = job["id"]
        cert_pem = job.get("issued_cert_pem")
        endpoint = job.get("endpoint") or {}
        endpoint_type = endpoint.get("endpoint_type")
        key_id = self._job_key_ids.get(job_id)

        if not cert_pem or not key_id:
            raise ProductionGateError(
                gate_name="CERT_DEPLOYMENT",
                message="Deployment requires issued_cert_pem and local key mapping for the renewal job.",
                remediation="Ensure CSR generation succeeds and job key mapping is persisted on the agent.",
            )

        key_pem = self.csr_generator.export_private_key_pem(key_id)
        logger.info(f"Deploying issued certificate for job {job_id} via {endpoint_type}")

        deployer = DeployerFactory.get_deployer(endpoint_type)
        deploy_args = {}

        if endpoint_type == "kubernetes":
            deploy_args = {
                "namespace": endpoint.get("k8s_namespace"),
                "secret_name": endpoint.get("k8s_secret_name"),
            }
        elif endpoint_type == "nginx":
            deploy_args = {
                "site_name": endpoint.get("name"),
            }
        elif endpoint_type == "envoy":
            deploy_args = {
                "listener_name": endpoint.get("name"),
            }
        else:
            raise ProductionGateError(
                gate_name="CERT_DEPLOYMENT",
                message=f"Unsupported endpoint_type for deployment: {endpoint_type}",
                remediation="Register a supported endpoint type or extend DeployerFactory.",
            )

        if not all(deploy_args.values()):
            raise ProductionGateError(
                gate_name="CERT_DEPLOYMENT",
                message=f"Missing deployment metadata for endpoint type {endpoint_type}.",
                remediation="Ensure endpoint metadata is configured (namespace/secret/site/listener).",
            )

        result = deployer.deploy(**deploy_args, cert_pem=cert_pem, key_pem=key_pem)
        if not result.success:
            raise ProductionGateError(
                gate_name="CERT_DEPLOYMENT",
                message=f"Deployment failed: {result.message}",
                remediation="Fix deployment target configuration and retry.",
            )

        self.client.signed_request("POST", "/api/v1/identity/agent/deploy-confirm", json_data={"job_id": job_id})
        logger.info(f"Confirmed deployment for job {job_id}")
