"""
OPS Signal Model schemas for TensorGuardFlow Robotics Integrations.

This module defines Pydantic models for bidirectional communication between
TensorGuardFlow and external robotics operations platforms.

Two canonical schemas:
1. OutboundOpsEvent - Events emitted from TGF to external tools
2. InboundOpsSignal - Signals received from external tools
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid
import hashlib
import json


# =============================================================================
# ENUMS
# =============================================================================

class Severity(str, Enum):
    """Event/signal severity levels."""
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class EventCategory(str, Enum):
    """Categories for outbound events."""
    CONTINUAL_LEARNING = "CONTINUAL_LEARNING"
    RELEASE = "RELEASE"
    TRUST = "TRUST"
    PRIVACY = "PRIVACY"
    INTEGRATION = "INTEGRATION"
    RUNTIME = "RUNTIME"


class OutboundEventType(str, Enum):
    """Types of outbound events."""
    # Continual Learning
    CANDIDATE_CREATED = "candidate_created"
    GATE_FAILED = "gate_failed"

    # Release
    PROMOTED = "promoted"
    ROLLBACK = "rollback"
    ROUTE_FROZEN = "route_frozen"
    ROUTE_UNFROZEN = "route_unfrozen"
    ADAPTER_QUARANTINED = "adapter_quarantined"

    # Runtime
    RESOLVE_DEGRADED = "resolve_degraded"

    # Trust
    EVIDENCE_INCOMPLETE = "evidence_incomplete"
    SIGNATURE_FAILED = "signature_failed"

    # Privacy
    PRIVACY_RECEIPT_FAILED = "privacy_receipt_failed"

    # Integration
    INTEGRATION_HEALTH_CHANGED = "integration_health_changed"
    OUTBOUND_DELIVERY_FAILED = "outbound_delivery_failed"


class SignalSource(str, Enum):
    """Sources of inbound signals."""
    INORBIT = "INORBIT"
    FORMANT = "FORMANT"
    FOXGLOVE = "FOXGLOVE"
    GENERIC = "GENERIC"


class InboundSignalType(str, Enum):
    """Types of inbound signals."""
    INCIDENT = "incident"
    REGRESSION_DETECTED = "regression_detected"
    DRIFT_DETECTED = "drift_detected"
    SAFETY_STOP = "safety_stop"
    TASK_FAILURE_SPIKE = "task_failure_spike"
    LATENCY_SPIKE = "latency_spike"
    MANUAL_ROLLBACK_REQUEST = "manual_rollback_request"
    FREEZE_REQUEST = "freeze_request"
    UNFREEZE_REQUEST = "unfreeze_request"
    ACKNOWLEDGE = "acknowledge"


class ActionType(str, Enum):
    """Actions that can be triggered by signals."""
    ROLLBACK_ROUTE = "rollback_route"
    FREEZE_ROUTE = "freeze_route"
    UNFREEZE_ROUTE = "unfreeze_route"
    QUARANTINE_ADAPTER = "quarantine_adapter"
    OPEN_INVESTIGATION = "open_investigation"
    ACKNOWLEDGE = "acknowledge"
    NO_ACTION = "no_action"


# =============================================================================
# OUTBOUND EVENT SCHEMAS
# =============================================================================

class EvidenceRefs(BaseModel):
    """References to evidence artifacts."""
    tgsp_uri: Optional[str] = Field(
        default=None,
        description="URI to TGSP package"
    )
    evidence_uri: Optional[str] = Field(
        default=None,
        description="URI to evidence bundle"
    )
    policy_hash: Optional[str] = Field(
        default=None,
        description="Hash of policy used for decision"
    )


class ActionContext(BaseModel):
    """Context for actions taken (rollback, freeze, etc.)."""
    triggered_by: str = Field(
        description="What triggered this action: 'auto', 'manual', 'ops_signal'"
    )
    reason: str = Field(
        description="Human-readable reason for the action"
    )
    previous_adapter_id: Optional[str] = Field(
        default=None,
        description="Adapter ID before the action"
    )
    rollback_target_adapter_id: Optional[str] = Field(
        default=None,
        description="Target adapter ID for rollback"
    )
    signal_id: Optional[str] = Field(
        default=None,
        description="ID of inbound signal that triggered this action"
    )


class EventPayload(BaseModel):
    """Payload for outbound events."""
    # Adapter Context
    adapter_id: Optional[str] = Field(
        default=None,
        description="Adapter identifier"
    )
    run_id: Optional[str] = Field(
        default=None,
        description="Training/evaluation run identifier"
    )
    base_model: Optional[str] = Field(
        default=None,
        description="Base model identifier"
    )

    # Metrics Snapshot
    metrics_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current metrics at event time"
    )

    # Evidence References
    evidence_refs: Optional[EvidenceRefs] = Field(
        default=None,
        description="References to evidence artifacts"
    )

    # Integration Topology
    integration_topology_fingerprint: Optional[str] = Field(
        default=None,
        description="SHA256 fingerprint of integration topology"
    )

    # Action Context
    action_context: Optional[ActionContext] = Field(
        default=None,
        description="Context for actions taken"
    )

    # Extended Fields (provider-specific)
    extended: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Provider-specific extended fields"
    )


class OutboundOpsEvent(BaseModel):
    """
    Canonical schema for events emitted from TensorGuardFlow to external
    robotics operations platforms.
    """
    # Required Fields
    event_id: str = Field(
        default_factory=lambda: f"evt_{uuid.uuid4().hex[:24]}",
        description="Unique event identifier"
    )
    ts: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO8601 timestamp"
    )
    tenant_id: str = Field(
        description="Tenant identifier"
    )
    route_key: str = Field(
        description="Route identifier"
    )

    # Event Classification
    severity: Severity = Field(
        description="Event severity: INFO, WARN, CRITICAL"
    )
    category: EventCategory = Field(
        description="Event category"
    )
    type: OutboundEventType = Field(
        description="Event type"
    )

    # Human-Readable Summary
    summary: str = Field(
        max_length=256,
        description="Human-readable event summary"
    )

    # Structured Payload
    payload: EventPayload = Field(
        default_factory=EventPayload,
        description="Event-specific payload data"
    )

    # Schema Version
    schema_version: str = Field(
        default="1.0",
        description="Schema version for compatibility"
    )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(exclude_none=True)

    def compute_idempotency_key(self) -> str:
        """Compute idempotency key for delivery deduplication."""
        return self.event_id

    def compute_checksum(self) -> str:
        """Compute SHA256 checksum of event content."""
        content = json.dumps(
            self.model_dump(exclude={"event_id"}),
            sort_keys=True,
            default=str
        )
        return hashlib.sha256(content.encode()).hexdigest()


# =============================================================================
# INBOUND SIGNAL SCHEMAS
# =============================================================================

class ThresholdViolation(BaseModel):
    """Details of a threshold violation."""
    metric_name: str = Field(
        description="Name of the metric that violated threshold"
    )
    current_value: float = Field(
        description="Current value of the metric"
    )
    threshold_value: float = Field(
        description="Threshold value that was violated"
    )
    direction: str = Field(
        description="Direction of violation: 'above' or 'below'"
    )

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        if v not in ("above", "below"):
            raise ValueError("direction must be 'above' or 'below'")
        return v


class NormalizedSignalData(BaseModel):
    """Normalized data extracted from raw signal payload."""
    # Metrics at signal time
    metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metrics at the time of the signal"
    )

    # Affected robots/agents
    affected_agents: Optional[List[str]] = Field(
        default=None,
        description="List of affected robot/agent IDs"
    )

    # Threshold violation details
    threshold_violation: Optional[ThresholdViolation] = Field(
        default=None,
        description="Details of threshold violation if applicable"
    )

    # Operator notes
    operator_notes: Optional[str] = Field(
        default=None,
        description="Notes from operator if provided"
    )

    # Suggested action from source platform
    suggested_action: Optional[str] = Field(
        default=None,
        description="Suggested action from source platform"
    )

    # Incident ID from source platform
    source_incident_id: Optional[str] = Field(
        default=None,
        description="Incident ID in the source platform"
    )


class SignalPayload(BaseModel):
    """Payload for inbound signals."""
    # Raw payload from source (preserved for audit)
    raw: Dict[str, Any] = Field(
        description="Raw payload from source platform"
    )

    # Normalized fields (extracted by connector)
    normalized: NormalizedSignalData = Field(
        default_factory=NormalizedSignalData,
        description="Normalized signal data"
    )


class AuthInfo(BaseModel):
    """Authentication/signature verification info."""
    signature_present: bool = Field(
        description="Whether a signature was present in the request"
    )
    verified: bool = Field(
        description="Whether signature verification passed"
    )
    key_id: Optional[str] = Field(
        default=None,
        description="Key ID used for verification"
    )
    verification_error: Optional[str] = Field(
        default=None,
        description="Error message if verification failed"
    )


class InboundOpsSignal(BaseModel):
    """
    Canonical schema for signals received from external robotics operations
    platforms that may trigger TensorGuardFlow actions.
    """
    # Required Fields
    signal_id: str = Field(
        default_factory=lambda: f"sig_{uuid.uuid4().hex[:24]}",
        description="Unique signal identifier (generated by TGF)"
    )
    ts: str = Field(
        description="ISO8601 timestamp of the original signal"
    )

    # Source Identification
    source: SignalSource = Field(
        description="Source platform"
    )

    # Tenant & Route Targeting
    tenant_id: Optional[str] = Field(
        default=None,
        description="Explicit tenant identifier"
    )
    tenant_hint: Optional[str] = Field(
        default=None,
        description="Hint for tenant lookup (e.g., robot ID)"
    )
    route_key: str = Field(
        description="Target route identifier"
    )

    # Signal Classification
    severity: Severity = Field(
        description="Signal severity: WARN or CRITICAL"
    )
    type: InboundSignalType = Field(
        description="Signal type"
    )

    # Payload
    payload: SignalPayload = Field(
        description="Signal payload"
    )

    # Authentication
    auth: AuthInfo = Field(
        description="Signature verification status"
    )

    # Replay Protection
    dedupe_key: str = Field(
        description="Unique key for replay protection/deduplication"
    )

    # Processing Status
    received_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="When TGF received this signal"
    )
    processed_at: Optional[str] = Field(
        default=None,
        description="When TGF finished processing this signal"
    )
    action_taken: Optional[ActionType] = Field(
        default=None,
        description="Action taken in response to this signal"
    )
    action_details: Optional[str] = Field(
        default=None,
        description="Details about the action taken"
    )

    # Schema Version
    schema_version: str = Field(
        default="1.0",
        description="Schema version for compatibility"
    )

    @model_validator(mode="after")
    def validate_tenant_identification(self) -> "InboundOpsSignal":
        """Ensure at least one tenant identifier is present."""
        if not self.tenant_id and not self.tenant_hint:
            raise ValueError(
                "At least one of tenant_id or tenant_hint must be provided"
            )
        return self

    @field_validator("severity")
    @classmethod
    def validate_severity_for_signal(cls, v: Severity) -> Severity:
        """Inbound signals should be WARN or CRITICAL (not INFO)."""
        if v == Severity.INFO:
            raise ValueError(
                "Inbound signals must have severity WARN or CRITICAL"
            )
        return v

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(exclude_none=True)

    def is_critical(self) -> bool:
        """Check if this is a critical signal."""
        return self.severity == Severity.CRITICAL

    def requires_immediate_action(self) -> bool:
        """Check if this signal requires immediate action."""
        immediate_types = {
            InboundSignalType.SAFETY_STOP,
            InboundSignalType.MANUAL_ROLLBACK_REQUEST,
        }
        return self.type in immediate_types or self.is_critical()


# =============================================================================
# RESULT SCHEMAS
# =============================================================================

class SendResult(BaseModel):
    """Result of sending an outbound event."""
    success: bool = Field(
        description="Whether delivery was successful"
    )
    event_id: str = Field(
        description="Event ID that was sent"
    )
    provider: str = Field(
        description="Target provider"
    )
    status_code: Optional[int] = Field(
        default=None,
        description="HTTP status code if applicable"
    )
    latency_ms: int = Field(
        description="Delivery latency in milliseconds"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if delivery failed"
    )
    retry_scheduled: bool = Field(
        default=False,
        description="Whether a retry has been scheduled"
    )
    dlq_id: Optional[str] = Field(
        default=None,
        description="DLQ entry ID if event was queued for retry"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump(exclude_none=True)


class IngestResult(BaseModel):
    """Result of ingesting an inbound signal."""
    success: bool = Field(
        description="Whether ingestion was successful"
    )
    signal_id: str = Field(
        description="Generated signal ID"
    )
    source: SignalSource = Field(
        description="Source platform"
    )
    action_taken: Optional[ActionType] = Field(
        default=None,
        description="Action taken in response"
    )
    action_details: Optional[str] = Field(
        default=None,
        description="Details about the action"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if ingestion failed"
    )
    signature_verified: bool = Field(
        default=False,
        description="Whether signature was verified"
    )
    is_replay: bool = Field(
        default=False,
        description="Whether this was detected as a replay"
    )


# =============================================================================
# SIGNAL TYPE TO ACTION MAPPING (Default)
# =============================================================================

DEFAULT_SIGNAL_ACTION_MAP: Dict[InboundSignalType, ActionType] = {
    InboundSignalType.INCIDENT: ActionType.OPEN_INVESTIGATION,
    InboundSignalType.REGRESSION_DETECTED: ActionType.ROLLBACK_ROUTE,
    InboundSignalType.DRIFT_DETECTED: ActionType.OPEN_INVESTIGATION,
    InboundSignalType.SAFETY_STOP: ActionType.QUARANTINE_ADAPTER,
    InboundSignalType.TASK_FAILURE_SPIKE: ActionType.ROLLBACK_ROUTE,
    InboundSignalType.LATENCY_SPIKE: ActionType.OPEN_INVESTIGATION,
    InboundSignalType.MANUAL_ROLLBACK_REQUEST: ActionType.ROLLBACK_ROUTE,
    InboundSignalType.FREEZE_REQUEST: ActionType.FREEZE_ROUTE,
    InboundSignalType.UNFREEZE_REQUEST: ActionType.UNFREEZE_ROUTE,
    InboundSignalType.ACKNOWLEDGE: ActionType.ACKNOWLEDGE,
}


def get_default_action_for_signal(
    signal_type: InboundSignalType,
    severity: Severity,
) -> ActionType:
    """
    Get the default action for a signal type and severity.

    For CRITICAL severity, may escalate the action.
    """
    base_action = DEFAULT_SIGNAL_ACTION_MAP.get(
        signal_type,
        ActionType.OPEN_INVESTIGATION
    )

    # Escalate for critical signals if not already a strong action
    if severity == Severity.CRITICAL:
        if base_action == ActionType.OPEN_INVESTIGATION:
            return ActionType.FREEZE_ROUTE

    return base_action
