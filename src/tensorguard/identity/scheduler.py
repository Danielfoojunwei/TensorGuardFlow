"""
Renewal Scheduler - Certificate Lifecycle Orchestration

Schedules and orchestrates certificate renewal workflows.
Uses APScheduler for background job management.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from sqlmodel import Session, select
import logging
import asyncio

from ..platform.models.identity_models import (
    IdentityRenewalJob,
    IdentityCertificate,
    IdentityEndpoint,
    IdentityPolicy,
    RenewalJobStatus,
    AuditAction,
)
from .policy_engine import PolicyEngine
from .audit import AuditService

logger = logging.getLogger(__name__)


class RenewalScheduler:
    """
    Certificate renewal orchestrator.
    
    Features:
    - Automatic renewal scheduling based on policy
    - State machine for renewal workflow
    - Retry logic with exponential backoff
    - Rollback support on failure
    - Idempotent operations
    """
    
    # Retry backoff multipliers
    RETRY_BACKOFF_MINUTES = [5, 15, 60, 240]  # 5min, 15min, 1hr, 4hr
    
    def __init__(self, session: Session):
        self.session = session
        self.policy_engine = PolicyEngine()
        self.audit_service = AuditService(session)
        
        # Callbacks for external integrations
        self._on_csr_request: Optional[Callable] = None
        self._on_challenge_start: Optional[Callable] = None
        self._on_deploy: Optional[Callable] = None
    
    def set_csr_callback(self, callback: Callable) -> None:
        """Set callback for CSR requests to agent."""
        self._on_csr_request = callback
    
    def set_challenge_callback(self, callback: Callable) -> None:
        """Set callback for challenge initiation."""
        self._on_challenge_start = callback
    
    def set_deploy_callback(self, callback: Callable) -> None:
        """Set callback for certificate deployment."""
        self._on_deploy = callback
    
    # === Job Creation ===
    
    def schedule_renewal(
        self,
        tenant_id: str,
        fleet_id: str,
        endpoint_id: str,
        policy_id: str,
        scheduled_at: Optional[datetime] = None,
        old_cert_id: Optional[str] = None,
    ) -> IdentityRenewalJob:
        """
        Schedule a new renewal job.
        
        Idempotent: won't create duplicate jobs for the same endpoint/policy.
        """
        # Check for existing pending job
        existing = self.session.exec(
            select(IdentityRenewalJob).where(
                IdentityRenewalJob.endpoint_id == endpoint_id,
                IdentityRenewalJob.status.in_([
                    RenewalJobStatus.PENDING,
                    RenewalJobStatus.CSR_REQUESTED,
                    RenewalJobStatus.CHALLENGE_PENDING,
                    RenewalJobStatus.ISSUING,
                ])
            )
        ).first()
        
        if existing:
            logger.info(f"Renewal job already exists for endpoint {endpoint_id}: {existing.id}")
            return existing
        
        job = IdentityRenewalJob(
            tenant_id=tenant_id,
            fleet_id=fleet_id,
            endpoint_id=endpoint_id,
            policy_id=policy_id,
            old_cert_id=old_cert_id,
            scheduled_at=scheduled_at or datetime.utcnow(),
            status=RenewalJobStatus.PENDING,
        )
        
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        
        # Audit
        self.audit_service.log(
            tenant_id=tenant_id,
            fleet_id=fleet_id,
            action=AuditAction.RENEWAL_STARTED,
            actor_type="scheduler",
            actor_id="system",
            target_type="renewal_job",
            target_id=job.id,
            payload={"endpoint_id": endpoint_id, "policy_id": policy_id},
        )
        
        logger.info(f"Scheduled renewal job: {job.id}")
        return job
    
    def get_job(self, job_id: str) -> Optional[IdentityRenewalJob]:
        """Get job by ID."""
        return self.session.get(IdentityRenewalJob, job_id)
    
    def list_jobs(
        self,
        tenant_id: str,
        fleet_id: Optional[str] = None,
        status: Optional[RenewalJobStatus] = None,
        limit: int = 100,
    ) -> List[IdentityRenewalJob]:
        """List renewal jobs with filters."""
        statement = select(IdentityRenewalJob).where(
            IdentityRenewalJob.tenant_id == tenant_id
        )
        
        if fleet_id:
            statement = statement.where(IdentityRenewalJob.fleet_id == fleet_id)
        if status:
            statement = statement.where(IdentityRenewalJob.status == status)
        
        statement = statement.order_by(IdentityRenewalJob.created_at.desc()).limit(limit)
        return list(self.session.exec(statement).all())
    
    # === State Machine ===
    
    def advance_job(self, job_id: str) -> IdentityRenewalJob:
        """
        Advance a job through its state machine.
        
        State transitions:
        PENDING → CSR_REQUESTED → CSR_RECEIVED → CHALLENGE_PENDING →
        CHALLENGE_COMPLETE → ISSUING → ISSUED → DEPLOYING → VALIDATING → SUCCEEDED
        
        On failure: → FAILED (can retry if attempts < max)
        On rollback: → ROLLED_BACK
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        
        if job.is_terminal:
            logger.info(f"Job {job_id} is already in terminal state: {job.status}")
            return job
        
        try:
            if job.status == RenewalJobStatus.PENDING:
                return self._request_csr(job)
            elif job.status == RenewalJobStatus.CSR_REQUESTED:
                # Waiting for agent to provide CSR
                return job
            elif job.status == RenewalJobStatus.CSR_RECEIVED:
                return self._start_challenge(job)
            elif job.status == RenewalJobStatus.CHALLENGE_PENDING:
                # Waiting for challenge completion
                return job
            elif job.status == RenewalJobStatus.CHALLENGE_COMPLETE:
                return self._issue_certificate(job)
            elif job.status == RenewalJobStatus.ISSUING:
                # Waiting for issuance
                return job
            elif job.status == RenewalJobStatus.ISSUED:
                return self._deploy_certificate(job)
            elif job.status == RenewalJobStatus.DEPLOYING:
                # Waiting for deployment
                return job
            elif job.status == RenewalJobStatus.VALIDATING:
                return self._validate_deployment(job)
            else:
                return job
                
        except Exception as e:
            return self._handle_failure(job, str(e))
    
    def _request_csr(self, job: IdentityRenewalJob) -> IdentityRenewalJob:
        """Request CSR from agent."""
        job.status = RenewalJobStatus.CSR_REQUESTED
        job.started_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        
        if self._on_csr_request:
            # Trigger agent to generate CSR
            self._on_csr_request(job)
        
        self.session.add(job)
        self.session.commit()
        
        logger.info(f"Job {job.id}: CSR requested")
        return job
    
    def receive_csr(self, job_id: str, csr_pem: str) -> IdentityRenewalJob:
        """Receive CSR from agent."""
        job = self.get_job(job_id)
        if not job or job.status != RenewalJobStatus.CSR_REQUESTED:
            raise ValueError(f"Invalid job state for CSR: {job_id}")
        
        job.csr_pem = csr_pem
        job.status = RenewalJobStatus.CSR_RECEIVED
        job.updated_at = datetime.utcnow()
        
        self.session.add(job)
        self.session.commit()
        
        self.audit_service.log(
            tenant_id=job.tenant_id,
            fleet_id=job.fleet_id,
            action=AuditAction.CSR_GENERATED,
            actor_type="agent",
            actor_id=job.endpoint_id,
            target_type="renewal_job",
            target_id=job.id,
        )
        
        logger.info(f"Job {job.id}: CSR received")
        return job
    
    def _start_challenge(self, job: IdentityRenewalJob) -> IdentityRenewalJob:
        """Initiate ACME challenge."""
        job.status = RenewalJobStatus.CHALLENGE_PENDING
        job.updated_at = datetime.utcnow()
        
        # Get policy for challenge type
        policy = self.session.get(IdentityPolicy, job.policy_id)
        if policy:
            job.challenge_type = policy.acme_challenge_type
        
        if self._on_challenge_start:
            self._on_challenge_start(job)
        
        self.session.add(job)
        self.session.commit()
        
        self.audit_service.log(
            tenant_id=job.tenant_id,
            fleet_id=job.fleet_id,
            action=AuditAction.CHALLENGE_STARTED,
            actor_type="scheduler",
            actor_id="system",
            target_type="renewal_job",
            target_id=job.id,
            payload={"challenge_type": job.challenge_type},
        )
        
        logger.info(f"Job {job.id}: Challenge started ({job.challenge_type})")
        return job
    
    def complete_challenge(self, job_id: str, token: str) -> IdentityRenewalJob:
        """Mark challenge as complete."""
        job = self.get_job(job_id)
        if not job or job.status != RenewalJobStatus.CHALLENGE_PENDING:
            raise ValueError(f"Invalid job state for challenge completion: {job_id}")
        
        job.challenge_token = token
        job.status = RenewalJobStatus.CHALLENGE_COMPLETE
        job.updated_at = datetime.utcnow()
        
        self.session.add(job)
        self.session.commit()
        
        self.audit_service.log(
            tenant_id=job.tenant_id,
            fleet_id=job.fleet_id,
            action=AuditAction.CHALLENGE_COMPLETED,
            actor_type="agent",
            actor_id=job.endpoint_id,
            target_type="renewal_job",
            target_id=job.id,
        )
        
        logger.info(f"Job {job.id}: Challenge completed")
        return job
    
    def _issue_certificate(self, job: IdentityRenewalJob) -> IdentityRenewalJob:
        """Issue certificate via ACME/CA."""
        job.status = RenewalJobStatus.ISSUING
        job.updated_at = datetime.utcnow()
        
        # Actual ACME issuance would happen here via ACMEClient
        # For now, mark as issuing and wait for external completion
        
        self.session.add(job)
        self.session.commit()
        
        logger.info(f"Job {job.id}: Issuing certificate")
        return job
    
    def receive_certificate(self, job_id: str, cert_pem: str, cert_id: str) -> IdentityRenewalJob:
        """Receive issued certificate."""
        job = self.get_job(job_id)
        if not job or job.status != RenewalJobStatus.ISSUING:
            raise ValueError(f"Invalid job state for certificate: {job_id}")
        
        job.issued_cert_pem = cert_pem
        job.new_cert_id = cert_id
        job.status = RenewalJobStatus.ISSUED
        job.updated_at = datetime.utcnow()
        
        self.session.add(job)
        self.session.commit()
        
        logger.info(f"Job {job.id}: Certificate issued")
        return job
    
    def _deploy_certificate(self, job: IdentityRenewalJob) -> IdentityRenewalJob:
        """Deploy certificate to endpoint."""
        job.status = RenewalJobStatus.DEPLOYING
        job.updated_at = datetime.utcnow()
        
        if self._on_deploy:
            self._on_deploy(job)
        
        self.session.add(job)
        self.session.commit()
        
        logger.info(f"Job {job.id}: Deploying certificate")
        return job
    
    def confirm_deployment(self, job_id: str) -> IdentityRenewalJob:
        """Agent confirms deployment is complete."""
        job = self.get_job(job_id)
        if not job or job.status != RenewalJobStatus.DEPLOYING:
            raise ValueError(f"Invalid job state for deployment confirmation: {job_id}")
        
        job.status = RenewalJobStatus.VALIDATING
        job.updated_at = datetime.utcnow()
        
        self.session.add(job)
        self.session.commit()
        
        logger.info(f"Job {job.id}: Deployment confirmed, validating")
        return job
    
    def _validate_deployment(self, job: IdentityRenewalJob) -> IdentityRenewalJob:
        """Validate deployment via health checks."""
        # In production, this would probe the endpoint
        # For now, mark as succeeded
        
        job.status = RenewalJobStatus.SUCCEEDED
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        
        self.session.add(job)
        self.session.commit()
        
        self.audit_service.log(
            tenant_id=job.tenant_id,
            fleet_id=job.fleet_id,
            action=AuditAction.RENEWAL_SUCCEEDED,
            actor_type="scheduler",
            actor_id="system",
            target_type="renewal_job",
            target_id=job.id,
            payload={"new_cert_id": job.new_cert_id},
        )
        
        logger.info(f"Job {job.id}: Renewal succeeded")
        return job
    
    def _handle_failure(self, job: IdentityRenewalJob, error: str) -> IdentityRenewalJob:
        """Handle job failure with retry logic."""
        job.last_error = error
        job.retry_count += 1
        job.updated_at = datetime.utcnow()
        
        if job.can_retry:
            # Schedule retry with backoff
            backoff_idx = min(job.retry_count - 1, len(self.RETRY_BACKOFF_MINUTES) - 1)
            backoff_minutes = self.RETRY_BACKOFF_MINUTES[backoff_idx]
            job.next_retry_at = datetime.utcnow() + timedelta(minutes=backoff_minutes)
            job.status = RenewalJobStatus.PENDING
            
            logger.warning(f"Job {job.id} failed, retry {job.retry_count} in {backoff_minutes}m: {error}")
        else:
            job.status = RenewalJobStatus.FAILED
            job.completed_at = datetime.utcnow()
            
            self.audit_service.log(
                tenant_id=job.tenant_id,
                fleet_id=job.fleet_id,
                action=AuditAction.RENEWAL_FAILED,
                actor_type="scheduler",
                actor_id="system",
                target_type="renewal_job",
                target_id=job.id,
                payload={"error": error, "retries": job.retry_count},
            )
            
            logger.error(f"Job {job.id} failed permanently: {error}")
        
        self.session.add(job)
        self.session.commit()
        return job
    
    def rollback_job(self, job_id: str, reason: str) -> IdentityRenewalJob:
        """Rollback a failed or problematic renewal."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        
        if not job.can_rollback:
            raise ValueError(f"Job {job_id} cannot be rolled back")
        
        # In production: restore old certificate
        # For now: just mark as rolled back
        
        job.status = RenewalJobStatus.ROLLED_BACK
        job.status_message = reason
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        
        self.session.add(job)
        self.session.commit()
        
        self.audit_service.log(
            tenant_id=job.tenant_id,
            fleet_id=job.fleet_id,
            action=AuditAction.RENEWAL_ROLLED_BACK,
            actor_type="scheduler",
            actor_id="system",
            target_type="renewal_job",
            target_id=job.id,
            payload={"reason": reason},
        )
        
        logger.info(f"Job {job.id} rolled back: {reason}")
        return job
    
    # === Scheduling ===
    
    def find_renewals_due(
        self,
        tenant_id: str,
        policy_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find certificates that are due for renewal based on policy.
        
        Returns list of {endpoint, certificate, policy, days_to_renewal}.
        """
        from .inventory import InventoryService
        
        inventory = InventoryService(self.session)
        certs = inventory.list_certificates(tenant_id)
        
        due_for_renewal = []
        
        for cert in certs:
            if cert.policy_id:
                policy = self.session.get(IdentityPolicy, cert.policy_id)
            elif policy_id:
                policy = self.session.get(IdentityPolicy, policy_id)
            else:
                continue
            
            if not policy:
                continue
            
            # Check if within renewal window
            renewal_date = self.policy_engine.calculate_renewal_date(cert, policy)
            if datetime.utcnow() >= renewal_date:
                endpoint = inventory.get_endpoint(cert.endpoint_id)
                due_for_renewal.append({
                    "endpoint": endpoint,
                    "certificate": cert,
                    "policy": policy,
                    "days_to_expiry": cert.days_to_expiry,
                })
        
        return due_for_renewal
    
    def run_scheduled_renewals(self, tenant_id: str) -> List[IdentityRenewalJob]:
        """
        Execute renewals for all certificates due.
        
        Returns list of created renewal jobs.
        """
        due = self.find_renewals_due(tenant_id)
        jobs = []
        
        for item in due:
            endpoint = item["endpoint"]
            cert = item["certificate"]
            policy = item["policy"]
            
            job = self.schedule_renewal(
                tenant_id=tenant_id,
                fleet_id=endpoint.fleet_id,
                endpoint_id=endpoint.id,
                policy_id=policy.id,
                old_cert_id=cert.id,
            )
            jobs.append(job)
        
        return jobs
