"""
Formant connector for TensorGuardFlow Robotics Ops Integrations.

Formant is a robotics data and operations platform that provides
fleet management, telemetry, and incident management. This connector enables:
- Outbound: Send TGF events to Formant as custom events/annotations
- Inbound: Receive Formant alerts and incidents that trigger TGF actions
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


class FormantConnector(RoboticsOpsConnector):
    """
    Formant robotics platform connector.

    Capabilities:
    - Send TGF events to Formant as custom annotations/events
    - Receive Formant webhook alerts (device issues, anomalies)
    - Acknowledge incidents in Formant
    - Map Formant device IDs to TGF routes

    API Reference: https://docs.formant.io/
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Formant connector."""
        super().__init__(config)
        self._provider_name = "formant"

        # Parse typed config if available
        if isinstance(config, RoboticsConnectorConfig):
            self._typed_config = config
        else:
            self._typed_config = RoboticsConnectorConfig(**config)

        # HTTP client for outbound requests
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def provider(self) -> str:
        return "formant"

    @property
    def display_name(self) -> str:
        return self._typed_config.get_display_name()

    def robotics_capabilities(self) -> List[RoboticsOpsCapability]:
        """Formant supports events, webhooks, incidents, and acknowledgment."""
        caps = [
            RoboticsOpsCapability.EVENTS_OUT,
            RoboticsOpsCapability.WEBHOOKS_IN,
            RoboticsOpsCapability.INCIDENT_CREATE,
            RoboticsOpsCapability.SIGNATURE_VERIFICATION,
        ]

        # Add acknowledgment if configured
        formant_config = self._typed_config.formant
        if formant_config and formant_config.supports_acknowledgment:
            caps.append(RoboticsOpsCapability.INCIDENT_ACKNOWLEDGE)

        return caps

    # -------------------------------------------------------------------------
    # CONFIGURATION VALIDATION
    # -------------------------------------------------------------------------

    def validate_config(self) -> ValidationResult:
        """Validate Formant connector configuration."""
        errors = []
        warnings = []
        suggestions = []

        # Run base validation
        base_errors = self._typed_config.validate_complete()
        errors.extend(base_errors)

        # Formant-specific validation
        formant_config = self._typed_config.formant
        if not formant_config:
            warnings.append(
                "Formant-specific configuration not provided. "
                "Using default settings."
            )
        else:
            if not formant_config.organization_id:
                suggestions.append(
                    "Consider setting formant.organization_id for "
                    "organization-scoped API calls."
                )

        # Check signature verification
        if self._typed_config.inbound.verify_signature:
            if not self._typed_config.inbound.signing_secret_ref:
                errors.append(
                    "Formant webhook signature verification enabled but "
                    "signing_secret_ref not configured."
                )
            else:
                if self._typed_config.inbound.signature_header_name != "X-Formant-Signature":
                    suggestions.append(
                        "Formant typically uses 'X-Formant-Signature' header. "
                        "Current: " + self._typed_config.inbound.signature_header_name
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
        """Check Formant connectivity and authentication."""
        start_time = time.time()

        try:
            client = await self._get_client()

            if self._typed_config.outbound.mode == OutboundMode.API:
                api_base = self._typed_config.outbound.api_base_url
                if api_base:
                    headers = await self._get_auth_headers()
                    response = await client.get(
                        f"{api_base.rstrip('/')}/v1/admin/health",
                        headers=headers,
                        timeout=10.0,
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if response.status_code == 200:
                        return HealthCheckResult(
                            status="OK",
                            message="Formant API is reachable and authenticated",
                            latency_ms=latency_ms,
                            details={"api_version": "v1"},
                        )
                    elif response.status_code == 401:
                        return HealthCheckResult(
                            status="FAIL",
                            message="Formant authentication failed",
                            latency_ms=latency_ms,
                        )
                    else:
                        return HealthCheckResult(
                            status="WARN",
                            message=f"Formant returned status {response.status_code}",
                            latency_ms=latency_ms,
                        )

            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                status="WARN",
                message="Formant webhook mode - connectivity not pre-validated",
                latency_ms=latency_ms,
            )

        except httpx.ConnectError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                status="FAIL",
                message=f"Failed to connect to Formant: {str(e)}",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                status="FAIL",
                message=f"Formant health check failed: {str(e)}",
                latency_ms=latency_ms,
            )

    # -------------------------------------------------------------------------
    # OUTBOUND: SEND EVENTS
    # -------------------------------------------------------------------------

    async def send_event(self, event: OutboundOpsEvent) -> SendResult:
        """Send an outbound event to Formant."""
        start_time = time.time()

        try:
            client = await self._get_client()
            payload = self._format_formant_payload(event)

            # Determine target URL
            if self._typed_config.outbound.mode == OutboundMode.WEBHOOK:
                url = self._typed_config.outbound.target_url
            else:
                api_base = self._typed_config.outbound.api_base_url
                url = f"{api_base.rstrip('/')}/v1/annotations"

            headers = await self._get_auth_headers()
            headers["Content-Type"] = "application/json"
            headers["X-TGF-Event-ID"] = event.event_id
            headers["X-TGF-Idempotency-Key"] = event.compute_idempotency_key()

            response = await self._send_with_retry(
                client, url, payload, headers
            )

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code in (200, 201, 202):
                return SendResult(
                    success=True,
                    event_id=event.event_id,
                    provider="formant",
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                )
            else:
                return SendResult(
                    success=False,
                    event_id=event.event_id,
                    provider="formant",
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    error=f"Formant returned {response.status_code}",
                    retry_scheduled=self._should_retry(response.status_code),
                )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                event_id=event.event_id,
                provider="formant",
                latency_ms=latency_ms,
                error=str(e),
                retry_scheduled=True,
            )

    def _format_formant_payload(self, event: OutboundOpsEvent) -> Dict[str, Any]:
        """Format event for Formant's annotation/event API."""
        # Formant uses annotations for custom events
        return {
            "type": "tensorguard_event",
            "timestamp": event.ts,
            "message": event.summary,
            "tags": {
                "event_id": event.event_id,
                "event_type": event.type.value,
                "category": event.category.value,
                "severity": event.severity.value,
                "route_key": event.route_key,
                "tenant_id": event.tenant_id,
            },
            "metadata": event.payload.model_dump(exclude_none=True),
            "source": "tensorguard",
        }

    # -------------------------------------------------------------------------
    # INCIDENT ACKNOWLEDGMENT
    # -------------------------------------------------------------------------

    async def acknowledge_incident(
        self,
        incident_id: str,
        message: Optional[str] = None,
    ) -> bool:
        """Acknowledge an incident in Formant."""
        formant_config = self._typed_config.formant
        if not formant_config or not formant_config.supports_acknowledgment:
            return False

        try:
            client = await self._get_client()
            api_base = self._typed_config.outbound.api_base_url

            if not api_base:
                return False

            url = f"{api_base.rstrip('/')}/v1/incidents/{incident_id}/acknowledge"
            headers = await self._get_auth_headers()
            headers["Content-Type"] = "application/json"

            payload = {
                "message": message or "Acknowledged by TensorGuardFlow",
                "source": "tensorguard",
            }

            response = await client.post(url, json=payload, headers=headers)
            return response.status_code in (200, 201, 204)

        except Exception:
            return False

    # -------------------------------------------------------------------------
    # INBOUND: INGEST SIGNALS
    # -------------------------------------------------------------------------

    async def ingest_signal(
        self,
        headers: Dict[str, str],
        body: bytes,
        source_ip: Optional[str] = None,
    ) -> IngestResult:
        """Ingest and normalize a Formant webhook signal."""
        try:
            # Verify signature
            auth_info = self._verify_formant_signature(headers, body)

            if self._typed_config.inbound.verify_signature and not auth_info.verified:
                return IngestResult(
                    success=False,
                    signal_id="",
                    source=SignalSource.FORMANT,
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
                    source=SignalSource.FORMANT,
                    error=f"Invalid JSON payload: {e}",
                    signature_verified=auth_info.verified,
                )

            # Normalize signal
            signal = self._normalize_formant_signal(raw_payload, auth_info)

            # Check replay
            if self._check_replay(signal.dedupe_key):
                return IngestResult(
                    success=False,
                    signal_id=signal.signal_id,
                    source=SignalSource.FORMANT,
                    error="Replay detected",
                    signature_verified=auth_info.verified,
                    is_replay=True,
                )

            return IngestResult(
                success=True,
                signal_id=signal.signal_id,
                source=SignalSource.FORMANT,
                signature_verified=auth_info.verified,
            )

        except Exception as e:
            return IngestResult(
                success=False,
                signal_id="",
                source=SignalSource.FORMANT,
                error=str(e),
            )

    def _verify_formant_signature(
        self,
        headers: Dict[str, str],
        body: bytes,
    ) -> AuthInfo:
        """Verify Formant webhook signature."""
        sig_header = (
            self._typed_config.formant.signature_header
            if self._typed_config.formant
            else "X-Formant-Signature"
        )
        return self._verify_signature(
            {**headers, "signature_header_name": sig_header},
            body,
        )

    def _normalize_formant_signal(
        self,
        raw_payload: Dict[str, Any],
        auth_info: AuthInfo,
    ) -> InboundOpsSignal:
        """Normalize Formant webhook payload to canonical signal."""
        # Extract Formant-specific fields
        event_type = raw_payload.get("type", "") or raw_payload.get("eventType", "")
        device_id = raw_payload.get("deviceId") or raw_payload.get("device_id")
        timestamp = raw_payload.get("timestamp") or raw_payload.get("time")

        # Convert timestamp
        if isinstance(timestamp, (int, float)):
            ts = datetime.utcfromtimestamp(timestamp / 1000).isoformat() + "Z"
        elif isinstance(timestamp, str):
            ts = timestamp
        else:
            ts = datetime.utcnow().isoformat() + "Z"

        # Map event type
        signal_type = self._map_formant_event_type(event_type)

        # Map severity
        severity = self._map_formant_severity(
            raw_payload.get("severity") or raw_payload.get("priority", "warn")
        )

        # Build normalized data
        normalized = NormalizedSignalData(
            metrics=raw_payload.get("metrics") or raw_payload.get("data"),
            affected_agents=[device_id] if device_id else None,
            operator_notes=raw_payload.get("message") or raw_payload.get("description"),
            source_incident_id=raw_payload.get("id") or raw_payload.get("incidentId"),
        )

        # Extract threshold violation if present
        alert_data = raw_payload.get("alert") or raw_payload.get("trigger", {})
        if alert_data and isinstance(alert_data, dict):
            if "threshold" in alert_data or "metric" in alert_data:
                normalized.threshold_violation = ThresholdViolation(
                    metric_name=alert_data.get("metric", "unknown"),
                    current_value=float(alert_data.get("value", 0)),
                    threshold_value=float(alert_data.get("threshold", 0)),
                    direction=alert_data.get("direction", "above"),
                )

        # Build dedupe key
        dedupe_key = f"formant:{raw_payload.get('id', '')}:{device_id or 'unknown'}"

        # Determine route key
        route_key = raw_payload.get("route_key")
        if not route_key:
            route_key = self._typed_config.mapping.default_route_key or "default"

        return InboundOpsSignal(
            ts=ts,
            source=SignalSource.FORMANT,
            tenant_id=raw_payload.get("tenant_id") or raw_payload.get("organizationId"),
            tenant_hint=device_id,
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

    def _map_formant_event_type(self, event_type: str) -> InboundSignalType:
        """Map Formant event type to canonical signal type."""
        event_type_lower = event_type.lower()

        # Formant-specific event type mappings
        mapping = {
            "device.alert.triggered": InboundSignalType.INCIDENT,
            "device.offline": InboundSignalType.INCIDENT,
            "device.error": InboundSignalType.INCIDENT,
            "stream.anomaly": InboundSignalType.DRIFT_DETECTED,
            "metric.threshold.exceeded": InboundSignalType.REGRESSION_DETECTED,
            "command.failed": InboundSignalType.TASK_FAILURE_SPIKE,
            "safety.event": InboundSignalType.SAFETY_STOP,
        }

        for pattern, signal_type in mapping.items():
            if pattern in event_type_lower:
                return signal_type

        return InboundSignalType.INCIDENT

    def _map_formant_severity(self, severity: str) -> Severity:
        """Map Formant severity to canonical severity."""
        severity_lower = severity.lower()

        if severity_lower in ("critical", "high", "urgent"):
            return Severity.CRITICAL
        elif severity_lower in ("warning", "warn", "medium"):
            return Severity.WARN
        else:
            return Severity.WARN

    # -------------------------------------------------------------------------
    # SMOKE TEST
    # -------------------------------------------------------------------------

    async def smoke_test(self) -> SmokeTestResult:
        """Run a smoke test for Formant connectivity."""
        start_time = time.time()

        try:
            validation = self.validate_config()
            if not validation.valid:
                return SmokeTestResult(
                    passed=False,
                    test_name="formant_smoke_test",
                    duration_ms=int((time.time() - start_time) * 1000),
                    message=f"Configuration invalid: {validation.errors}",
                )

            health = await self.health_check()
            duration_ms = int((time.time() - start_time) * 1000)

            if health.is_healthy():
                return SmokeTestResult(
                    passed=True,
                    test_name="formant_smoke_test",
                    duration_ms=duration_ms,
                    message="Formant connectivity verified",
                    details=health.details,
                )
            else:
                return SmokeTestResult(
                    passed=False,
                    test_name="formant_smoke_test",
                    duration_ms=duration_ms,
                    message=health.message,
                )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="formant_smoke_test",
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
        """Export Formant integration artifacts."""
        artifacts = await super().export_artifacts(context)

        manifest = {
            "provider": "formant",
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
                    "incident", "drift_detected", "regression_detected",
                ],
            },
            "features": {
                "supports_acknowledgment": (
                    self._typed_config.formant.supports_acknowledgment
                    if self._typed_config.formant else False
                ),
            },
            "context": {
                "route_key": context.get("route_key"),
                "run_id": context.get("run_id"),
            },
        }

        artifacts.append(ExportArtifact(
            name="formant-integration-manifest.json",
            content=json.dumps(manifest, indent=2),
            artifact_type="json",
            metadata={"provider": "formant"},
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
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code < 500 and response.status_code != 429:
                    return response

                if response.status_code not in retry_policy.retry_on_status_codes:
                    return response

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exception = e

            if attempt < retry_policy.max_retries:
                delay_ms = retry_policy.get_delay_ms(attempt)
                await asyncio.sleep(delay_ms / 1000)

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
