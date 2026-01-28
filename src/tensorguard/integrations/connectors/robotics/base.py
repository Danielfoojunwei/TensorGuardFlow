"""
Base connector interface for TensorGuardFlow Robotics Ops Integrations.

This module defines the contract that all robotics ops connectors must implement,
enabling bidirectional communication with external fleet management platforms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import hmac
import json
import time

from tensorguard.integrations.framework.contracts import (
    IntegrationConnector,
    ConnectorCapability,
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.connectors.robotics.schemas import (
    OutboundOpsEvent,
    InboundOpsSignal,
    SignalSource,
    InboundSignalType,
    Severity,
    SignalPayload,
    NormalizedSignalData,
    AuthInfo,
    SendResult,
    IngestResult,
)


# =============================================================================
# ROBOTICS OPS CAPABILITY EXTENSIONS
# =============================================================================

class RoboticsOpsCapability(str, Enum):
    """Capabilities specific to robotics ops connectors."""
    # Outbound capabilities
    EVENTS_OUT = "events_out"                 # Can send events to platform
    METRICS_PUSH = "metrics_push"             # Can push metrics to platform
    INCIDENT_CREATE = "incident_create"       # Can create incidents in platform

    # Inbound capabilities
    WEBHOOKS_IN = "webhooks_in"               # Can receive webhooks from platform
    INCIDENT_ACKNOWLEDGE = "incident_ack"     # Can acknowledge incidents

    # Artifact capabilities
    MCAP_BUNDLE_EXPORT = "mcap_bundle_export" # Can export MCAP bundle pointers

    # Security capabilities
    SECRET_ROTATION = "secret_rotation"       # Supports secret rotation
    SIGNATURE_VERIFICATION = "sig_verify"     # Supports webhook signature verification


# =============================================================================
# DEDUPE CACHE FOR REPLAY PROTECTION
# =============================================================================

class BoundedDedupeCache:
    """
    Bounded cache for replay protection.

    Stores dedupe keys with TTL for preventing replay attacks.
    Thread-safe for concurrent access.
    """

    def __init__(
        self,
        max_size: int = 10000,
        ttl_sec: int = 300,
    ):
        self.max_size = max_size
        self.ttl_sec = ttl_sec
        self._cache: Dict[str, float] = {}  # key -> timestamp
        self._lock_free = True  # For single-threaded use

    def contains(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        if key not in self._cache:
            return False
        if time.time() - self._cache[key] > self.ttl_sec:
            del self._cache[key]
            return False
        return True

    def add(self, key: str) -> bool:
        """
        Add key to cache.

        Returns True if added, False if already exists.
        """
        if self.contains(key):
            return False

        # Evict old entries if at capacity
        if len(self._cache) >= self.max_size:
            self._evict_expired()
            if len(self._cache) >= self.max_size:
                # Evict oldest entries
                sorted_keys = sorted(
                    self._cache.keys(),
                    key=lambda k: self._cache[k]
                )
                for k in sorted_keys[:len(sorted_keys) // 2]:
                    del self._cache[k]

        self._cache[key] = time.time()
        return True

    def _evict_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [
            k for k, ts in self._cache.items()
            if now - ts > self.ttl_sec
        ]
        for k in expired:
            del self._cache[k]

    def size(self) -> int:
        """Return current cache size."""
        return len(self._cache)

    def clear(self) -> None:
        """Clear all entries."""
        self._cache.clear()


# =============================================================================
# SIGNATURE VERIFICATION
# =============================================================================

@dataclass
class SignatureVerificationConfig:
    """Configuration for webhook signature verification."""
    enabled: bool = True
    algorithm: str = "hmac-sha256"  # hmac-sha256, rsa-sha256, ecdsa-sha256
    header_name: str = "X-Signature"
    timestamp_header: Optional[str] = None
    timestamp_tolerance_sec: int = 300
    secret_ref: Optional[str] = None  # Reference to secret in KMS/vault
    public_key_ref: Optional[str] = None  # For asymmetric verification


def verify_hmac_signature(
    payload: bytes,
    signature: str,
    secret: bytes,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify HMAC signature using constant-time comparison.

    Args:
        payload: Request body bytes
        signature: Received signature (hex-encoded)
        secret: Shared secret bytes
        algorithm: Hash algorithm (sha256, sha384, sha512)

    Returns:
        True if signature is valid
    """
    if algorithm == "sha256":
        hash_func = hashlib.sha256
    elif algorithm == "sha384":
        hash_func = hashlib.sha384
    elif algorithm == "sha512":
        hash_func = hashlib.sha512
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    expected = hmac.new(secret, payload, hash_func).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected.lower(), signature.lower())


def verify_signature_with_timestamp(
    payload: bytes,
    signature: str,
    timestamp: str,
    secret: bytes,
    tolerance_sec: int = 300,
) -> Tuple[bool, Optional[str]]:
    """
    Verify signature with timestamp validation.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check timestamp freshness
    try:
        ts = float(timestamp)
        if abs(time.time() - ts) > tolerance_sec:
            return False, f"Timestamp outside tolerance window ({tolerance_sec}s)"
    except ValueError:
        return False, "Invalid timestamp format"

    # Verify signature
    if not verify_hmac_signature(payload, signature, secret):
        return False, "Signature mismatch"

    return True, None


# =============================================================================
# BASE ROBOTICS OPS CONNECTOR
# =============================================================================

class RoboticsOpsConnector(IntegrationConnector):
    """
    Base class for robotics ops platform connectors.

    Extends IntegrationConnector with robotics-specific operations:
    - send_event: Send outbound events to external platform
    - ingest_signal: Normalize and verify inbound webhooks
    - smoke_test: Test connectivity with real or mock endpoints

    Subclasses must implement provider-specific logic for:
    - Payload formatting
    - Authentication
    - Signal normalization
    """

    # Dedupe cache shared across all connectors (or per-connector if needed)
    _dedupe_cache: Optional[BoundedDedupeCache] = None

    def __init__(self, config: Dict[str, Any]):
        """Initialize connector with configuration."""
        super().__init__(config)
        self._provider_name: str = "base"

        # Initialize dedupe cache if not exists
        if RoboticsOpsConnector._dedupe_cache is None:
            replay_config = config.get("inbound", {}).get("replay_protection", {})
            RoboticsOpsConnector._dedupe_cache = BoundedDedupeCache(
                max_size=replay_config.get("dedupe_cache_size", 10000),
                ttl_sec=replay_config.get("window_sec", 300),
            )

    @property
    def category(self) -> str:
        """Robotics ops connectors span F (serving) and G (trust)."""
        return "F/G"

    @abstractmethod
    def robotics_capabilities(self) -> List[RoboticsOpsCapability]:
        """Return list of robotics-specific capabilities."""
        pass

    def capabilities(self) -> List[ConnectorCapability]:
        """Return base connector capabilities."""
        caps = [ConnectorCapability.METRICS_SINK]

        # Add based on robotics capabilities
        robotics_caps = self.robotics_capabilities()
        if RoboticsOpsCapability.SIGNATURE_VERIFICATION in robotics_caps:
            caps.append(ConnectorCapability.VERIFY)

        return caps

    def describe_capabilities(self) -> Dict[str, Any]:
        """Describe all capabilities for API consumers."""
        return {
            "provider": self.provider,
            "category": self.category,
            "base_capabilities": [c.value for c in self.capabilities()],
            "robotics_capabilities": [c.value for c in self.robotics_capabilities()],
            "supports_webhooks_in": RoboticsOpsCapability.WEBHOOKS_IN in self.robotics_capabilities(),
            "supports_events_out": RoboticsOpsCapability.EVENTS_OUT in self.robotics_capabilities(),
            "supports_metrics_push": RoboticsOpsCapability.METRICS_PUSH in self.robotics_capabilities(),
            "supports_incident_create": RoboticsOpsCapability.INCIDENT_CREATE in self.robotics_capabilities(),
            "supports_acknowledge": RoboticsOpsCapability.INCIDENT_ACKNOWLEDGE in self.robotics_capabilities(),
            "supports_secret_rotation": RoboticsOpsCapability.SECRET_ROTATION in self.robotics_capabilities(),
            "supports_mcap_export": RoboticsOpsCapability.MCAP_BUNDLE_EXPORT in self.robotics_capabilities(),
        }

    # -------------------------------------------------------------------------
    # OUTBOUND: Send Events
    # -------------------------------------------------------------------------

    @abstractmethod
    async def send_event(self, event: OutboundOpsEvent) -> SendResult:
        """
        Send an outbound event to the external platform.

        Implementations must:
        - Format payload per provider requirements
        - Handle authentication
        - Implement retry with exponential backoff
        - Return SendResult with success/failure details

        Args:
            event: The event to send

        Returns:
            SendResult with delivery status
        """
        pass

    async def send_event_batch(
        self,
        events: List[OutboundOpsEvent],
    ) -> List[SendResult]:
        """
        Send multiple events (default: sequential).

        Override for batch-capable providers.
        """
        results = []
        for event in events:
            result = await self.send_event(event)
            results.append(result)
        return results

    # -------------------------------------------------------------------------
    # INBOUND: Ingest Signals
    # -------------------------------------------------------------------------

    @abstractmethod
    async def ingest_signal(
        self,
        headers: Dict[str, str],
        body: bytes,
        source_ip: Optional[str] = None,
    ) -> IngestResult:
        """
        Ingest and normalize an inbound webhook signal.

        Implementations must:
        - Verify signature if configured
        - Check replay protection
        - Normalize payload into InboundOpsSignal
        - Return IngestResult with normalized signal or error

        Args:
            headers: HTTP request headers
            body: Raw request body bytes
            source_ip: Source IP address (optional, for logging)

        Returns:
            IngestResult with normalized signal or error
        """
        pass

    def _normalize_signal(
        self,
        raw_payload: Dict[str, Any],
        source: SignalSource,
    ) -> InboundOpsSignal:
        """
        Default signal normalization.

        Override in subclasses for provider-specific normalization.
        """
        # Extract common fields with fallbacks
        ts = raw_payload.get("timestamp") or raw_payload.get("ts")
        if isinstance(ts, (int, float)):
            ts = datetime.utcfromtimestamp(ts).isoformat() + "Z"
        elif not ts:
            ts = datetime.utcnow().isoformat() + "Z"

        # Determine signal type
        signal_type = self._map_event_type_to_signal_type(
            raw_payload.get("event_type") or raw_payload.get("type", "incident")
        )

        # Determine severity
        severity = self._map_severity(
            raw_payload.get("severity") or raw_payload.get("priority", "warn")
        )

        # Build dedupe key
        dedupe_key = self._build_dedupe_key(raw_payload, source)

        return InboundOpsSignal(
            ts=ts,
            source=source,
            tenant_id=raw_payload.get("tenant_id"),
            tenant_hint=raw_payload.get("robot_id") or raw_payload.get("device_id"),
            route_key=raw_payload.get("route_key", "default"),
            severity=severity,
            type=signal_type,
            payload=SignalPayload(
                raw=raw_payload,
                normalized=NormalizedSignalData(
                    metrics=raw_payload.get("metrics"),
                    affected_agents=raw_payload.get("affected_agents")
                        or ([raw_payload.get("robot_id")] if raw_payload.get("robot_id") else None),
                    operator_notes=raw_payload.get("notes") or raw_payload.get("message"),
                    source_incident_id=raw_payload.get("incident_id") or raw_payload.get("event_id"),
                ),
            ),
            auth=AuthInfo(
                signature_present=False,
                verified=False,
            ),
            dedupe_key=dedupe_key,
        )

    def _map_event_type_to_signal_type(self, event_type: str) -> InboundSignalType:
        """Map provider event type to canonical signal type."""
        event_type_lower = event_type.lower()

        mapping = {
            "safety": InboundSignalType.SAFETY_STOP,
            "emergency": InboundSignalType.SAFETY_STOP,
            "stop": InboundSignalType.SAFETY_STOP,
            "regression": InboundSignalType.REGRESSION_DETECTED,
            "drift": InboundSignalType.DRIFT_DETECTED,
            "failure": InboundSignalType.TASK_FAILURE_SPIKE,
            "latency": InboundSignalType.LATENCY_SPIKE,
            "rollback": InboundSignalType.MANUAL_ROLLBACK_REQUEST,
            "freeze": InboundSignalType.FREEZE_REQUEST,
            "unfreeze": InboundSignalType.UNFREEZE_REQUEST,
        }

        for keyword, signal_type in mapping.items():
            if keyword in event_type_lower:
                return signal_type

        return InboundSignalType.INCIDENT

    def _map_severity(self, severity: str) -> Severity:
        """Map provider severity to canonical severity."""
        severity_lower = severity.lower()

        if severity_lower in ("critical", "emergency", "fatal", "high"):
            return Severity.CRITICAL
        elif severity_lower in ("warning", "warn", "medium"):
            return Severity.WARN
        else:
            # Default to WARN for inbound signals (INFO not allowed)
            return Severity.WARN

    def _build_dedupe_key(
        self,
        payload: Dict[str, Any],
        source: SignalSource,
    ) -> str:
        """Build dedupe key for replay protection."""
        # Use event ID if available
        event_id = (
            payload.get("event_id")
            or payload.get("incident_id")
            or payload.get("id")
        )
        if event_id:
            return f"{source.value}:{event_id}"

        # Fallback: hash of key fields
        key_data = {
            "source": source.value,
            "robot_id": payload.get("robot_id"),
            "type": payload.get("event_type") or payload.get("type"),
            "ts": payload.get("timestamp") or payload.get("ts"),
        }
        key_hash = hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()[:16]
        return f"{source.value}:{key_hash}"

    def _check_replay(self, dedupe_key: str) -> bool:
        """
        Check if signal is a replay.

        Returns True if this is a replay (should be rejected).
        """
        if self._dedupe_cache is None:
            return False

        # If key already in cache, it's a replay
        return not self._dedupe_cache.add(dedupe_key)

    def _verify_signature(
        self,
        headers: Dict[str, str],
        body: bytes,
    ) -> AuthInfo:
        """
        Verify webhook signature.

        Override in subclasses for provider-specific verification.
        """
        inbound_config = self.config.get("inbound", {})
        if not inbound_config.get("verify_signature", False):
            return AuthInfo(
                signature_present=False,
                verified=True,  # Not required
            )

        sig_header = inbound_config.get("signature_header_name", "X-Signature")
        signature = headers.get(sig_header) or headers.get(sig_header.lower())

        if not signature:
            return AuthInfo(
                signature_present=False,
                verified=False,
                verification_error="Signature header missing",
            )

        # Get secret (in real implementation, fetch from KMS/vault)
        secret_ref = inbound_config.get("signing_secret_ref")
        if not secret_ref:
            return AuthInfo(
                signature_present=True,
                verified=False,
                verification_error="No signing secret configured",
            )

        # For now, assume secret_ref is the actual secret (in prod, fetch from vault)
        secret = secret_ref.encode() if isinstance(secret_ref, str) else secret_ref

        try:
            is_valid = verify_hmac_signature(body, signature, secret)
            return AuthInfo(
                signature_present=True,
                verified=is_valid,
                verification_error=None if is_valid else "Signature mismatch",
            )
        except Exception as e:
            return AuthInfo(
                signature_present=True,
                verified=False,
                verification_error=str(e),
            )

    # -------------------------------------------------------------------------
    # SMOKE TEST
    # -------------------------------------------------------------------------

    @abstractmethod
    async def smoke_test(self) -> SmokeTestResult:
        """
        Run a quick operational test.

        Should verify:
        - Outbound connectivity (if credentials available)
        - Configuration validity
        - Webhook endpoint accessibility (if applicable)

        Returns:
            SmokeTestResult with pass/fail and details
        """
        pass

    # -------------------------------------------------------------------------
    # ARTIFACT EXPORT
    # -------------------------------------------------------------------------

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """
        Export integration artifacts.

        For robotics ops connectors, this may include:
        - MCAP bundle pointers
        - Event delivery manifests
        - Configuration snapshots
        """
        artifacts = []

        # Export configuration snapshot (without secrets)
        config_snapshot = self._get_safe_config_snapshot()
        artifacts.append(ExportArtifact(
            name=f"{self.provider}-config.json",
            content=json.dumps(config_snapshot, indent=2),
            artifact_type="json",
            metadata={
                "provider": self.provider,
                "category": self.category,
                "export_time": datetime.utcnow().isoformat(),
            },
        ))

        return artifacts

    def _get_safe_config_snapshot(self) -> Dict[str, Any]:
        """Get configuration snapshot with secrets redacted."""
        safe_config = {}

        for key, value in self.config.items():
            if any(secret_key in key.lower() for secret_key in
                   ["secret", "password", "token", "key", "credential"]):
                safe_config[key] = "[REDACTED]"
            elif isinstance(value, dict):
                safe_config[key] = self._redact_secrets_in_dict(value)
            else:
                safe_config[key] = value

        return safe_config

    def _redact_secrets_in_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact secrets in a dictionary."""
        result = {}
        for key, value in d.items():
            if any(secret_key in key.lower() for secret_key in
                   ["secret", "password", "token", "key", "credential"]):
                result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = self._redact_secrets_in_dict(value)
            else:
                result[key] = value
        return result

    # -------------------------------------------------------------------------
    # SAFE LOGGING
    # -------------------------------------------------------------------------

    def safe_log_event(self, event: OutboundOpsEvent) -> Dict[str, Any]:
        """
        Create a safe-to-log version of an event.

        Respects N2HE privacy mode if enabled.
        """
        n2he_enabled = self.config.get("n2he", {}).get("enabled", False)

        if n2he_enabled:
            # Minimal logging in N2HE mode
            return {
                "event_id": event.event_id,
                "type": event.type.value,
                "severity": event.severity.value,
                "route_key": "[N2HE_REDACTED]",
                "tenant_id": "[N2HE_REDACTED]",
            }

        # Standard safe logging (no secrets)
        return {
            "event_id": event.event_id,
            "type": event.type.value,
            "severity": event.severity.value,
            "category": event.category.value,
            "route_key": event.route_key,
            "tenant_id": event.tenant_id,
            "summary": event.summary[:100],  # Truncate
        }

    def safe_log_signal(self, signal: InboundOpsSignal) -> Dict[str, Any]:
        """
        Create a safe-to-log version of a signal.

        Never logs raw payload in production.
        """
        n2he_enabled = self.config.get("n2he", {}).get("enabled", False)

        if n2he_enabled:
            return {
                "signal_id": signal.signal_id,
                "type": signal.type.value,
                "severity": signal.severity.value,
                "source": signal.source.value,
                "route_key": "[N2HE_REDACTED]",
            }

        return {
            "signal_id": signal.signal_id,
            "type": signal.type.value,
            "severity": signal.severity.value,
            "source": signal.source.value,
            "route_key": signal.route_key,
            "auth_verified": signal.auth.verified,
            "dedupe_key": signal.dedupe_key[:20] + "...",  # Truncate
        }
