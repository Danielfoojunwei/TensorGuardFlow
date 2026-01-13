"""
Forensics Service

Provides forensics-grade logging with cryptographic signatures for audit trails.
Supports PQC (Post-Quantum Cryptography) signatures for tamper-evident records.

Used for adapter swaps, rollbacks, and other security-critical events.
"""

import json
import logging
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Session

from ..models.core import AuditLog
from ..models.telemetry_models import ForensicsEvent

logger = logging.getLogger(__name__)

# PQC implementation status
# In production, this would use a proper PQC library like liboqs or pqcrypto
# For now, we use SHA-512 with a secret key as a placeholder
PQC_SECRET_KEY = os.environ.get("TG_PQC_SECRET_KEY", "default-pqc-secret-key")


class ForensicsService:
    """
    Service for creating and verifying forensics-grade audit records.

    Features:
    - PQC signature generation for tamper evidence
    - Structured forensics event storage
    - Audit trail integration
    """

    def __init__(self, session: Session):
        self.session = session

    def sign_and_log(
        self,
        tenant_id: str,
        fleet_id: str,
        device_id: str,
        event_type: str,
        deployment_id: str,
        adapter_id: str,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> ForensicsEvent:
        """
        Create a forensics-grade event with PQC signature.

        Args:
            tenant_id: Tenant ID
            fleet_id: Fleet ID
            device_id: Device ID that initiated the event
            event_type: Type of event (adapter_swap, rollback, etc.)
            deployment_id: ID of the deployment
            adapter_id: ID of the adapter involved
            details: Additional event details
            user_id: User ID if event was user-initiated

        Returns:
            ForensicsEvent record with PQC signature
        """
        timestamp = datetime.utcnow()
        details_dict = details or {}

        # Compute PQC signature
        pqc_signature = self._compute_pqc_signature(
            deployment_id=deployment_id,
            adapter_id=adapter_id,
            timestamp=timestamp
        )

        # Create forensics event
        event = ForensicsEvent(
            tenant_id=tenant_id,
            fleet_id=fleet_id,
            device_id=device_id,
            event_type=event_type,
            deployment_id=deployment_id,
            adapter_id=adapter_id,
            details_json=json.dumps(details_dict),
            pqc_signature=pqc_signature,
            ts=timestamp
        )

        self.session.add(event)

        # Also log to audit trail
        self._log_to_audit(
            tenant_id=tenant_id,
            event_type=event_type,
            deployment_id=deployment_id,
            adapter_id=adapter_id,
            device_id=device_id,
            user_id=user_id,
            pqc_signature=pqc_signature
        )

        self.session.commit()
        self.session.refresh(event)

        logger.info(
            f"Forensics event logged: type={event_type}, "
            f"deployment={deployment_id}, device={device_id}, "
            f"signature={pqc_signature[:16]}..."
        )

        return event

    def verify_signature(self, event: ForensicsEvent) -> bool:
        """
        Verify the PQC signature of a forensics event.

        Args:
            event: ForensicsEvent to verify

        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = self._compute_pqc_signature(
            deployment_id=event.deployment_id,
            adapter_id=event.adapter_id,
            timestamp=event.ts
        )

        is_valid = event.pqc_signature == expected_signature

        if not is_valid:
            logger.warning(
                f"Forensics event signature verification failed: "
                f"event_id={event.id}, expected={expected_signature[:16]}..., "
                f"actual={event.pqc_signature[:16]}..."
            )

        return is_valid

    def log_adapter_swap(
        self,
        tenant_id: str,
        fleet_id: str,
        device_id: str,
        deployment_id: str,
        previous_adapter_id: str,
        new_adapter_id: str,
        is_rollback: bool = False,
        user_id: Optional[str] = None
    ) -> ForensicsEvent:
        """
        Log an adapter swap event with forensics-grade signature.

        Args:
            tenant_id: Tenant ID
            fleet_id: Fleet ID
            device_id: Device ID
            deployment_id: Deployment ID
            previous_adapter_id: ID of the adapter being replaced
            new_adapter_id: ID of the new adapter
            is_rollback: Whether this is a rollback operation
            user_id: User ID if manually triggered

        Returns:
            ForensicsEvent record
        """
        event_type = "rollback" if is_rollback else "adapter_swap"

        return self.sign_and_log(
            tenant_id=tenant_id,
            fleet_id=fleet_id,
            device_id=device_id,
            event_type=event_type,
            deployment_id=deployment_id,
            adapter_id=new_adapter_id,
            details={
                "previous_adapter_id": previous_adapter_id,
                "new_adapter_id": new_adapter_id,
                "is_rollback": is_rollback,
            },
            user_id=user_id
        )

    def log_deployment_event(
        self,
        tenant_id: str,
        fleet_id: str,
        deployment_id: str,
        event_type: str,
        adapter_id: str,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> ForensicsEvent:
        """
        Log a deployment lifecycle event.

        Args:
            tenant_id: Tenant ID
            fleet_id: Fleet ID
            deployment_id: Deployment ID
            event_type: Event type (deployment_start, deployment_promote, etc.)
            adapter_id: Target adapter ID
            details: Additional details
            user_id: User ID who triggered the event

        Returns:
            ForensicsEvent record
        """
        return self.sign_and_log(
            tenant_id=tenant_id,
            fleet_id=fleet_id,
            device_id="platform",  # Platform-initiated events
            event_type=event_type,
            deployment_id=deployment_id,
            adapter_id=adapter_id,
            details=details,
            user_id=user_id
        )

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _compute_pqc_signature(
        self,
        deployment_id: str,
        adapter_id: str,
        timestamp: datetime
    ) -> str:
        """
        Compute PQC signature for forensics event.

        Signature format: pqc-sha512:<hex-digest>

        Note: In production, this would use a proper PQC algorithm like
        CRYSTALS-Dilithium or SPHINCS+. For now, we use HMAC-SHA512 as a
        placeholder that provides the same tamper-detection properties.
        """
        # Canonical timestamp format
        ts_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Message to sign: deployment_id + adapter_id + timestamp
        message = f"{deployment_id}:{adapter_id}:{ts_str}"

        # HMAC-SHA512 with PQC secret key
        import hmac
        signature_bytes = hmac.new(
            PQC_SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha512
        ).digest()

        # Return with algorithm prefix for future compatibility
        return f"pqc-sha512:{signature_bytes.hex()}"

    def _log_to_audit(
        self,
        tenant_id: str,
        event_type: str,
        deployment_id: str,
        adapter_id: str,
        device_id: str,
        user_id: Optional[str],
        pqc_signature: str
    ):
        """Log forensics event to main audit trail."""
        try:
            entry = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=f"FORENSICS_{event_type.upper()}",
                resource_id=deployment_id,
                resource_type="deployment",
                details=json.dumps({
                    "adapter_id": adapter_id,
                    "device_id": device_id,
                    "pqc_signature": pqc_signature,
                }),
                success=True
            )
            self.session.add(entry)

        except Exception as e:
            logger.error(f"Failed to log forensics event to audit: {e}")


def compute_pqc_signature_standalone(
    deployment_id: str,
    adapter_id: str,
    timestamp: datetime
) -> str:
    """
    Standalone function to compute PQC signature.

    Can be used by edge agents without creating a service instance.
    """
    ts_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    message = f"{deployment_id}:{adapter_id}:{ts_str}"

    import hmac
    signature_bytes = hmac.new(
        PQC_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha512
    ).digest()

    return f"pqc-sha512:{signature_bytes.hex()}"
