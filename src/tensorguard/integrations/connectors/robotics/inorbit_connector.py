"""
InOrbit connector for TensorGuardFlow Robotics Ops Integrations.

InOrbit is a cloud-based robot operations platform for managing and monitoring
robot fleets. This connector enables:
- Outbound: Send TGF events (promotions, rollbacks, etc.) to InOrbit
- Inbound: Receive InOrbit incidents/alerts that trigger TGF actions
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from tensorguard.integrations.framework.contracts import (
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.connectors.robotics.base import (
    RoboticsOpsConnector,
    RoboticsOpsCapability,
)
from tensorguard.integrations.connectors.robotics.schemas import (
    OutboundOpsEvent,
    InboundOpsSignal,
    SignalSource,
    InboundSignalType,
    Severity,
    SignalPayload,
    NormalizedSignalData,
    ThresholdViolation,
    AuthInfo,
    SendResult,
    IngestResult,
)
from tensorguard.integrations.connectors.robotics.config import (
    RoboticsConnectorConfig,
    RoboticsProvider,
    OutboundMode,
    AuthType,
)


class InOrbitConnector(RoboticsOpsConnector):
    """
    InOrbit fleet management platform connector.

    Capabilities:
    - Send TGF events to InOrbit as custom events/annotations
    - Receive InOrbit webhook events (robot incidents, safety stops)
    - Map InOrbit robot IDs to TGF routes

    API Reference: https://docs.inorbit.ai/
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize InOrbit connector."""
        super().__init__(config)
        self._provider_name = "inorbit"

        # Parse typed config if available
        if isinstance(config, RoboticsConnectorConfig):
            self._typed_config = config
        else:
            self._typed_config = RoboticsConnectorConfig(**config)

        # HTTP client for outbound requests
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def provider(self) -> str:
        return "inorbit"

    @property
    def display_name(self) -> str:
        return self._typed_config.get_display_name()

    def robotics_capabilities(self) -> List[RoboticsOpsCapability]:
        """InOrbit supports events, webhooks, and incidents."""
        return [
            RoboticsOpsCapability.EVENTS_OUT,
            RoboticsOpsCapability.WEBHOOKS_IN,
            RoboticsOpsCapability.INCIDENT_CREATE,
            RoboticsOpsCapability.SIGNATURE_VERIFICATION,
        ]

    # -------------------------------------------------------------------------
    # CONFIGURATION VALIDATION
    # -------------------------------------------------------------------------

    def validate_config(self) -> ValidationResult:
        """Validate InOrbit connector configuration."""
        errors = []
        warnings = []
        suggestions = []

        # Run base validation
        base_errors = self._typed_config.validate_complete()
        errors.extend(base_errors)

        # InOrbit-specific validation
        inorbit_config = self._typed_config.inorbit
        if not inorbit_config:
            warnings.append(
                "InOrbit-specific configuration not provided. "
                "Using default settings."
            )
        else:
            if not inorbit_config.organization_id:
                suggestions.append(
                    "Consider setting inorbit.organization_id for "
                    "organization-scoped API calls."
                )

        # Check signature verification
        if self._typed_config.inbound.verify_signature:
            if not self._typed_config.inbound.signing_secret_ref:
                errors.append(
                    "InOrbit webhook signature verification enabled but "
                    "signing_secret_ref not configured."
                )
            else:
                # Suggest using X-InOrbit-Signature header
                if self._typed_config.inbound.signature_header_name != "X-InOrbit-Signature":
                    suggestions.append(
                        "InOrbit typically uses 'X-InOrbit-Signature' header. "
                        "Current setting: " + self._typed_config.inbound.signature_header_name
                    )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    # -------------------------------------------------------------------------
    # HEALTH CHECK
    # -------------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Check InOrbit connectivity and authentication."""
        start_time = time.time()

        try:
            client = await self._get_client()

            # For API mode, try to call a lightweight endpoint
            if self._typed_config.outbound.mode == OutboundMode.API:
                api_base = self._typed_config.outbound.api_base_url
                if api_base:
                    # Use a health/status endpoint if available
                    response = await client.get(
                        f"{api_base.rstrip('/')}/health",
                        timeout=10.0,
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if response.status_code == 200:
                        return HealthCheckResult(
                            status="OK",
                            message="InOrbit API is reachable and authenticated",
                            latency_ms=latency_ms,
                            details={"api_version": "v1"},
                        )
                    elif response.status_code == 401:
                        return HealthCheckResult(
                            status="FAIL",
                            message="InOrbit authentication failed",
                            latency_ms=latency_ms,
                            details={"status_code": response.status_code},
                        )
                    else:
                        return HealthCheckResult(
                            status="WARN",
                            message=f"InOrbit returned status {response.status_code}",
                            latency_ms=latency_ms,
                        )

            # For webhook mode, we can't directly test (target receives from us)
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                status="WARN",
                message="InOrbit webhook mode - connectivity cannot be pre-validated",
                latency_ms=latency_ms,
                details={"mode": "webhook"},
            )

        except httpx.ConnectError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                status="FAIL",
                message=f"Failed to connect to InOrbit: {str(e)}",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                status="FAIL",
                message=f"InOrbit health check failed: {str(e)}",
                latency_ms=latency_ms,
            )

    # -------------------------------------------------------------------------
    # OUTBOUND: SEND EVENTS
    # -------------------------------------------------------------------------

    async def send_event(self, event: OutboundOpsEvent) -> SendResult:
        """Send an outbound event to InOrbit."""
        start_time = time.time()

        try:
            client = await self._get_client()
            payload = self._format_inorbit_payload(event)

            # Determine target URL
            if self._typed_config.outbound.mode == OutboundMode.WEBHOOK:
                url = self._typed_config.outbound.target_url
            else:
                api_base = self._typed_config.outbound.api_base_url
                url = f"{api_base.rstrip('/')}/events"

            # Add authentication headers
            headers = await self._get_auth_headers()
            headers["Content-Type"] = "application/json"
            headers["X-TGF-Event-ID"] = event.event_id
            headers["X-TGF-Idempotency-Key"] = event.compute_idempotency_key()

            # Send with retry
            response = await self._send_with_retry(
                client, url, payload, headers
            )

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code in (200, 201, 202):
                return SendResult(
                    success=True,
                    event_id=event.event_id,
                    provider="inorbit",
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                )
            else:
                return SendResult(
                    success=False,
                    event_id=event.event_id,
                    provider="inorbit",
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    error=f"InOrbit returned {response.status_code}",
                    retry_scheduled=self._should_retry(response.status_code),
                )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                event_id=event.event_id,
                provider="inorbit",
                latency_ms=latency_ms,
                error=str(e),
                retry_scheduled=True,
            )

    def _format_inorbit_payload(self, event: OutboundOpsEvent) -> Dict[str, Any]:
        """Format event for InOrbit's expected payload structure."""
        return {
            "eventType": f"tensorguard.{event.type.value}",
            "timestamp": event.ts,
            "severity": event.severity.value.lower(),
            "data": {
                "event_id": event.event_id,
                "tenant_id": event.tenant_id,
                "route_key": event.route_key,
                "category": event.category.value,
                "summary": event.summary,
                "payload": event.payload.model_dump(exclude_none=True),
            },
            "source": "tensorguard",
            "version": event.schema_version,
        }

    # -------------------------------------------------------------------------
    # INBOUND: INGEST SIGNALS
    # -------------------------------------------------------------------------

    async def ingest_signal(
        self,
        headers: Dict[str, str],
        body: bytes,
        source_ip: Optional[str] = None,
    ) -> IngestResult:
        """Ingest and normalize an InOrbit webhook signal."""
        try:
            # Verify signature
            auth_info = self._verify_inorbit_signature(headers, body)

            if self._typed_config.inbound.verify_signature and not auth_info.verified:
                return IngestResult(
                    success=False,
                    signal_id="",
                    source=SignalSource.INORBIT,
                    error=auth_info.verification_error or "Signature verification failed",
                    signature_verified=False,
                )

            # Parse payload
            try:
                raw_payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as e:
                return IngestResult(
                    success=False,
                    signal_id="",
                    source=SignalSource.INORBIT,
                    error=f"Invalid JSON payload: {e}",
                    signature_verified=auth_info.verified,
                )

            # Normalize signal
            signal = self._normalize_inorbit_signal(raw_payload, auth_info)

            # Check replay
            if self._check_replay(signal.dedupe_key):
                return IngestResult(
                    success=False,
                    signal_id=signal.signal_id,
                    source=SignalSource.INORBIT,
                    error="Replay detected - signal already processed",
                    signature_verified=auth_info.verified,
                    is_replay=True,
                )

            return IngestResult(
                success=True,
                signal_id=signal.signal_id,
                source=SignalSource.INORBIT,
                signature_verified=auth_info.verified,
            )

        except Exception as e:
            return IngestResult(
                success=False,
                signal_id="",
                source=SignalSource.INORBIT,
                error=str(e),
            )

    def _verify_inorbit_signature(
        self,
        headers: Dict[str, str],
        body: bytes,
    ) -> AuthInfo:
        """Verify InOrbit webhook signature."""
        sig_header = (
            self._typed_config.inorbit.signature_header
            if self._typed_config.inorbit
            else "X-InOrbit-Signature"
        )
        return self._verify_signature(
            {**headers, "signature_header_name": sig_header},
            body,
        )

    def _normalize_inorbit_signal(
        self,
        raw_payload: Dict[str, Any],
        auth_info: AuthInfo,
    ) -> InboundOpsSignal:
        """Normalize InOrbit webhook payload to canonical signal."""
        # Extract InOrbit-specific fields
        event_type = raw_payload.get("eventType", "")
        robot_id = raw_payload.get("robotId") or raw_payload.get("robot_id")
        timestamp = raw_payload.get("timestamp")

        # Convert timestamp
        if isinstance(timestamp, (int, float)):
            # InOrbit uses milliseconds
            ts = datetime.utcfromtimestamp(timestamp / 1000).isoformat() + "Z"
        elif isinstance(timestamp, str):
            ts = timestamp
        else:
            ts = datetime.utcnow().isoformat() + "Z"

        # Map event type
        signal_type = self._map_inorbit_event_type(event_type)

        # Map severity
        severity = self._map_inorbit_severity(
            raw_payload.get("severity") or raw_payload.get("level", "warn")
        )

        # Build normalized data
        normalized = NormalizedSignalData(
            metrics=raw_payload.get("metrics"),
            affected_agents=[robot_id] if robot_id else None,
            operator_notes=raw_payload.get("message") or raw_payload.get("description"),
            source_incident_id=raw_payload.get("incidentId") or raw_payload.get("eventId"),
        )

        # Extract threshold violation if present
        if "threshold" in raw_payload or "violation" in raw_payload:
            threshold_data = raw_payload.get("threshold") or raw_payload.get("violation", {})
            if threshold_data:
                normalized.threshold_violation = ThresholdViolation(
                    metric_name=threshold_data.get("metric", "unknown"),
                    current_value=float(threshold_data.get("value", 0)),
                    threshold_value=float(threshold_data.get("threshold", 0)),
                    direction=threshold_data.get("direction", "above"),
                )

        # Build dedupe key
        dedupe_key = (
            f"inorbit:{raw_payload.get('eventId', '')}:{robot_id or 'unknown'}"
        )

        # Determine route key from mapping or payload
        route_key = raw_payload.get("route_key")
        if not route_key:
            route_key = self._typed_config.mapping.default_route_key or "default"

        return InboundOpsSignal(
            ts=ts,
            source=SignalSource.INORBIT,
            tenant_id=raw_payload.get("tenant_id"),
            tenant_hint=robot_id,
            route_key=route_key,
            severity=severity,
            type=signal_type,
            payload=SignalPayload(
                raw=raw_payload,
                normalized=normalized,
            ),
            auth=auth_info,
            dedupe_key=dedupe_key,
        )

    def _map_inorbit_event_type(self, event_type: str) -> InboundSignalType:
        """Map InOrbit event type to canonical signal type."""
        event_type_lower = event_type.lower()

        # InOrbit-specific event type mappings
        mapping = {
            "robot.safety.triggered": InboundSignalType.SAFETY_STOP,
            "robot.emergency.stop": InboundSignalType.SAFETY_STOP,
            "robot.collision.detected": InboundSignalType.SAFETY_STOP,
            "robot.task.failed": InboundSignalType.TASK_FAILURE_SPIKE,
            "robot.task.timeout": InboundSignalType.TASK_FAILURE_SPIKE,
            "metric.threshold.exceeded": InboundSignalType.REGRESSION_DETECTED,
            "robot.offline": InboundSignalType.INCIDENT,
            "robot.error": InboundSignalType.INCIDENT,
            "fleet.alert": InboundSignalType.INCIDENT,
        }

        for pattern, signal_type in mapping.items():
            if pattern in event_type_lower:
                return signal_type

        return InboundSignalType.INCIDENT

    def _map_inorbit_severity(self, severity: str) -> Severity:
        """Map InOrbit severity to canonical severity."""
        severity_lower = severity.lower()

        if severity_lower in ("critical", "emergency", "high"):
            return Severity.CRITICAL
        elif severity_lower in ("warning", "warn", "medium"):
            return Severity.WARN
        else:
            return Severity.WARN  # Default to WARN for inbound

    # -------------------------------------------------------------------------
    # SMOKE TEST
    # -------------------------------------------------------------------------

    async def smoke_test(self) -> SmokeTestResult:
        """Run a smoke test for InOrbit connectivity."""
        start_time = time.time()

        try:
            # Check configuration validity first
            validation = self.validate_config()
            if not validation.valid:
                return SmokeTestResult(
                    passed=False,
                    test_name="inorbit_smoke_test",
                    duration_ms=int((time.time() - start_time) * 1000),
                    message=f"Configuration invalid: {validation.errors}",
                )

            # Run health check
            health = await self.health_check()

            duration_ms = int((time.time() - start_time) * 1000)

            if health.is_healthy():
                return SmokeTestResult(
                    passed=True,
                    test_name="inorbit_smoke_test",
                    duration_ms=duration_ms,
                    message="InOrbit connectivity verified",
                    details=health.details,
                )
            else:
                return SmokeTestResult(
                    passed=False,
                    test_name="inorbit_smoke_test",
                    duration_ms=duration_ms,
                    message=health.message,
                    details=health.details,
                )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="inorbit_smoke_test",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Smoke test failed: {str(e)}",
            )

    # -------------------------------------------------------------------------
    # ARTIFACT EXPORT
    # -------------------------------------------------------------------------

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export InOrbit integration artifacts."""
        artifacts = await super().export_artifacts(context)

        # Add InOrbit-specific integration manifest
        manifest = {
            "provider": "inorbit",
            "version": "1.0",
            "capabilities": [c.value for c in self.robotics_capabilities()],
            "outbound": {
                "mode": self._typed_config.outbound.mode.value,
                "event_types": [
                    "candidate_created", "gate_failed", "promoted",
                    "rollback", "route_frozen", "route_unfrozen",
                ],
            },
            "inbound": {
                "webhook_path": self._typed_config.inbound.webhook_path,
                "signal_types": [
                    "safety_stop", "task_failure_spike", "incident",
                ],
            },
            "context": {
                "route_key": context.get("route_key"),
                "run_id": context.get("run_id"),
            },
        }

        artifacts.append(ExportArtifact(
            name="inorbit-integration-manifest.json",
            content=json.dumps(manifest, indent=2),
            artifact_type="json",
            metadata={"provider": "inorbit"},
        ))

        return artifacts

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._typed_config.outbound.timeout_ms / 1000,
            )
        return self._client

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        headers = dict(self._typed_config.outbound.headers)

        auth_type = self._typed_config.outbound.auth_type
        secret_ref = self._typed_config.outbound.secret_ref

        if auth_type == AuthType.BEARER and secret_ref:
            # In production, fetch from KMS/vault
            # For now, assume secret_ref is the token
            headers["Authorization"] = f"Bearer {secret_ref}"
        elif auth_type == AuthType.API_KEY and secret_ref:
            headers["X-API-Key"] = secret_ref

        return headers

    async def _send_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> httpx.Response:
        """Send request with exponential backoff retry."""
        retry_policy = self._typed_config.outbound.retry_policy
        last_exception: Optional[Exception] = None

        for attempt in range(retry_policy.max_retries + 1):
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                )

                # Don't retry on client errors (4xx except 429)
                if response.status_code < 500 and response.status_code != 429:
                    return response

                # Check if we should retry this status code
                if response.status_code not in retry_policy.retry_on_status_codes:
                    return response

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exception = e

            # Wait before retry
            if attempt < retry_policy.max_retries:
                delay_ms = retry_policy.get_delay_ms(attempt)
                await asyncio.sleep(delay_ms / 1000)

        # Return last response or raise last exception
        if last_exception:
            raise last_exception
        return response

    def _should_retry(self, status_code: int) -> bool:
        """Check if status code should trigger retry."""
        return status_code in self._typed_config.outbound.retry_policy.retry_on_status_codes

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
