"""
Foxglove connector for TensorGuardFlow Robotics Ops Integrations.

Foxglove is a robotics visualization and recording platform. Unlike InOrbit
and Formant, Foxglove primarily acts as a visualization/recording sink.

This connector enables:
- Outbound: Send TGF events to Foxglove webhook/ingest endpoints
- Export: Generate MCAP bundle pointers linking TGF artifacts to Foxglove
- Inbound: Optional webhook support for custom Foxglove integrations
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


class FoxgloveConnector(RoboticsOpsConnector):
    """
    Foxglove visualization/recording platform connector.

    Foxglove differs from fleet management platforms:
    - Primarily a visualization and recording sink
    - Focuses on MCAP format for robotics data
    - Less emphasis on real-time incident management

    Capabilities:
    - Send TGF events to configured webhook endpoints
    - Export MCAP bundle pointers linking evidence to Foxglove
    - Optional inbound webhook support

    API Reference: https://docs.foxglove.dev/
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Foxglove connector."""
        super().__init__(config)
        self._provider_name = "foxglove"

        # Parse typed config if available
        if isinstance(config, RoboticsConnectorConfig):
            self._typed_config = config
        else:
            self._typed_config = RoboticsConnectorConfig(**config)

        # HTTP client for outbound requests
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def provider(self) -> str:
        return "foxglove"

    @property
    def display_name(self) -> str:
        return self._typed_config.get_display_name()

    def robotics_capabilities(self) -> List[RoboticsOpsCapability]:
        """Foxglove capabilities - focused on events and MCAP export."""
        caps = [
            RoboticsOpsCapability.EVENTS_OUT,
            RoboticsOpsCapability.MCAP_BUNDLE_EXPORT,
        ]

        # Add webhook support if configured
        if self._typed_config.inbound.verify_signature:
            caps.append(RoboticsOpsCapability.WEBHOOKS_IN)
            caps.append(RoboticsOpsCapability.SIGNATURE_VERIFICATION)

        return caps

    # -------------------------------------------------------------------------
    # CONFIGURATION VALIDATION
    # -------------------------------------------------------------------------

    def validate_config(self) -> ValidationResult:
        """Validate Foxglove connector configuration."""
        errors = []
        warnings = []
        suggestions = []

        # Run base validation
        base_errors = self._typed_config.validate_complete()
        errors.extend(base_errors)

        # Foxglove-specific validation
        foxglove_config = self._typed_config.foxglove
        if not foxglove_config:
            warnings.append(
                "Foxglove-specific configuration not provided. "
                "Using default settings."
            )
        else:
            # Check MCAP export configuration
            if foxglove_config.enable_mcap_export:
                if not foxglove_config.mcap_storage_base:
                    warnings.append(
                        "MCAP export enabled but mcap_storage_base not set. "
                        "Bundle pointers will use relative paths."
                    )
                else:
                    suggestions.append(
                        "MCAP bundle pointers will reference: "
                        f"{foxglove_config.mcap_storage_base}"
                    )

        # Foxglove often uses generic webhooks
        if self._typed_config.outbound.mode == OutboundMode.WEBHOOK:
            if not self._typed_config.outbound.target_url:
                errors.append(
                    "Foxglove webhook mode requires target_url."
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
        """Check Foxglove connectivity."""
        start_time = time.time()

        try:
            client = await self._get_client()

            # For webhook mode, try a HEAD request to verify endpoint exists
            if self._typed_config.outbound.mode == OutboundMode.WEBHOOK:
                target_url = self._typed_config.outbound.target_url
                if target_url:
                    try:
                        response = await client.head(target_url, timeout=10.0)
                        latency_ms = int((time.time() - start_time) * 1000)

                        # Accept any 2xx or 405 (method not allowed but endpoint exists)
                        if response.status_code < 400 or response.status_code == 405:
                            return HealthCheckResult(
                                status="OK",
                                message="Foxglove webhook endpoint is reachable",
                                latency_ms=latency_ms,
                            )
                        else:
                            return HealthCheckResult(
                                status="WARN",
                                message=f"Foxglove endpoint returned {response.status_code}",
                                latency_ms=latency_ms,
                            )
                    except httpx.ConnectError:
                        latency_ms = int((time.time() - start_time) * 1000)
                        return HealthCheckResult(
                            status="FAIL",
                            message="Cannot connect to Foxglove webhook endpoint",
                            latency_ms=latency_ms,
                        )

            # For API mode
            if self._typed_config.outbound.mode == OutboundMode.API:
                api_base = self._typed_config.outbound.api_base_url
                if api_base:
                    headers = await self._get_auth_headers()
                    response = await client.get(
                        f"{api_base.rstrip('/')}/v1/health",
                        headers=headers,
                        timeout=10.0,
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if response.status_code == 200:
                        return HealthCheckResult(
                            status="OK",
                            message="Foxglove API is reachable",
                            latency_ms=latency_ms,
                        )
                    else:
                        return HealthCheckResult(
                            status="WARN",
                            message=f"Foxglove API returned {response.status_code}",
                            latency_ms=latency_ms,
                        )

            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                status="UNKNOWN",
                message="Foxglove connector configured but no endpoint to test",
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                status="FAIL",
                message=f"Foxglove health check failed: {str(e)}",
                latency_ms=latency_ms,
            )

    # -------------------------------------------------------------------------
    # OUTBOUND: SEND EVENTS
    # -------------------------------------------------------------------------

    async def send_event(self, event: OutboundOpsEvent) -> SendResult:
        """Send an outbound event to Foxglove."""
        start_time = time.time()

        try:
            client = await self._get_client()
            payload = self._format_foxglove_payload(event)

            # Determine target URL
            if self._typed_config.outbound.mode == OutboundMode.WEBHOOK:
                url = self._typed_config.outbound.target_url
            else:
                api_base = self._typed_config.outbound.api_base_url
                url = f"{api_base.rstrip('/')}/v1/events"

            if not url:
                return SendResult(
                    success=False,
                    event_id=event.event_id,
                    provider="foxglove",
                    latency_ms=int((time.time() - start_time) * 1000),
                    error="No target URL configured",
                )

            headers = await self._get_auth_headers()
            headers["Content-Type"] = "application/json"
            headers["X-TGF-Event-ID"] = event.event_id

            response = await self._send_with_retry(
                client, url, payload, headers
            )

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code in (200, 201, 202, 204):
                return SendResult(
                    success=True,
                    event_id=event.event_id,
                    provider="foxglove",
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                )
            else:
                return SendResult(
                    success=False,
                    event_id=event.event_id,
                    provider="foxglove",
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    error=f"Foxglove returned {response.status_code}",
                    retry_scheduled=self._should_retry(response.status_code),
                )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                event_id=event.event_id,
                provider="foxglove",
                latency_ms=latency_ms,
                error=str(e),
                retry_scheduled=True,
            )

    def _format_foxglove_payload(self, event: OutboundOpsEvent) -> Dict[str, Any]:
        """Format event for Foxglove webhook/API."""
        # Generic webhook format that Foxglove can ingest
        return {
            "event_type": f"tensorguard.{event.type.value}",
            "timestamp": event.ts,
            "severity": event.severity.value,
            "source": "tensorguard",
            "data": {
                "event_id": event.event_id,
                "tenant_id": event.tenant_id,
                "route_key": event.route_key,
                "category": event.category.value,
                "summary": event.summary,
                "payload": event.payload.model_dump(exclude_none=True),
            },
            "schema_version": event.schema_version,
        }

    # -------------------------------------------------------------------------
    # MCAP BUNDLE EXPORT
    # -------------------------------------------------------------------------

    def generate_mcap_bundle_pointer(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate MCAP bundle pointer for Foxglove integration.

        This creates a metadata file that links TGF artifacts to MCAP recordings,
        allowing operators to view evidence alongside robot recordings.
        """
        foxglove_config = self._typed_config.foxglove
        mcap_base = (
            foxglove_config.mcap_storage_base
            if foxglove_config else None
        ) or ""

        route_key = context.get("route_key", "unknown")
        run_id = context.get("run_id", "unknown")
        adapter_id = context.get("adapter_id")

        # Build artifact references
        artifact_refs = []

        # TGSP package reference
        if context.get("tgsp_uri"):
            artifact_refs.append({
                "type": "tgsp_package",
                "uri": context["tgsp_uri"],
                "description": "TensorGuard Secure Package",
            })

        # Evidence bundle reference
        if context.get("evidence_uri"):
            artifact_refs.append({
                "type": "evidence_bundle",
                "uri": context["evidence_uri"],
                "description": "Evidence chain artifacts",
            })

        # Metrics snapshot
        if context.get("metrics_uri"):
            artifact_refs.append({
                "type": "metrics",
                "uri": context["metrics_uri"],
                "description": "Training/evaluation metrics",
            })

        return {
            "format": "mcap_bundle_pointer",
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "source": "tensorguard",
            "mcap": {
                "storage_base": mcap_base,
                "suggested_path": f"{route_key}/{run_id}/recordings/",
            },
            "tensorguard": {
                "route_key": route_key,
                "run_id": run_id,
                "adapter_id": adapter_id,
                "artifacts": artifact_refs,
            },
            "foxglove": {
                "layout_suggestion": "tensorguard_evidence_panel",
                "panel_config": {
                    "show_metrics": True,
                    "show_evidence_chain": True,
                    "link_to_recordings": True,
                },
            },
        }

    # -------------------------------------------------------------------------
    # INBOUND: INGEST SIGNALS (OPTIONAL)
    # -------------------------------------------------------------------------

    async def ingest_signal(
        self,
        headers: Dict[str, str],
        body: bytes,
        source_ip: Optional[str] = None,
    ) -> IngestResult:
        """Ingest a Foxglove webhook signal (optional integration)."""
        try:
            # Foxglove typically doesn't send webhooks, but we support generic format
            auth_info = self._verify_signature(headers, body)

            if self._typed_config.inbound.verify_signature and not auth_info.verified:
                return IngestResult(
                    success=False,
                    signal_id="",
                    source=SignalSource.FOXGLOVE,
                    error=auth_info.verification_error or "Signature verification failed",
                    signature_verified=False,
                )

            try:
                raw_payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as e:
                return IngestResult(
                    success=False,
                    signal_id="",
                    source=SignalSource.FOXGLOVE,
                    error=f"Invalid JSON payload: {e}",
                    signature_verified=auth_info.verified,
                )

            # Normalize using generic handler
            signal = self._normalize_signal(raw_payload, SignalSource.FOXGLOVE)
            signal.auth = auth_info

            # Check replay
            if self._check_replay(signal.dedupe_key):
                return IngestResult(
                    success=False,
                    signal_id=signal.signal_id,
                    source=SignalSource.FOXGLOVE,
                    error="Replay detected",
                    signature_verified=auth_info.verified,
                    is_replay=True,
                )

            return IngestResult(
                success=True,
                signal_id=signal.signal_id,
                source=SignalSource.FOXGLOVE,
                signature_verified=auth_info.verified,
            )

        except Exception as e:
            return IngestResult(
                success=False,
                signal_id="",
                source=SignalSource.FOXGLOVE,
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # SMOKE TEST
    # -------------------------------------------------------------------------

    async def smoke_test(self) -> SmokeTestResult:
        """Run a smoke test for Foxglove connectivity."""
        start_time = time.time()

        try:
            validation = self.validate_config()
            if not validation.valid:
                return SmokeTestResult(
                    passed=False,
                    test_name="foxglove_smoke_test",
                    duration_ms=int((time.time() - start_time) * 1000),
                    message=f"Configuration invalid: {validation.errors}",
                )

            # Test health
            health = await self.health_check()
            duration_ms = int((time.time() - start_time) * 1000)

            # Test MCAP pointer generation
            mcap_pointer = self.generate_mcap_bundle_pointer({
                "route_key": "test-route",
                "run_id": "test-run",
            })

            if health.is_healthy():
                return SmokeTestResult(
                    passed=True,
                    test_name="foxglove_smoke_test",
                    duration_ms=duration_ms,
                    message="Foxglove connectivity and MCAP export verified",
                    details={
                        "health": health.to_dict(),
                        "mcap_pointer_sample": mcap_pointer,
                    },
                )
            else:
                # If no outbound configured, still pass if MCAP export works
                foxglove_config = self._typed_config.foxglove
                if foxglove_config and foxglove_config.enable_mcap_export:
                    return SmokeTestResult(
                        passed=True,
                        test_name="foxglove_smoke_test",
                        duration_ms=duration_ms,
                        message="MCAP export available (outbound not configured)",
                        details={"mcap_pointer_sample": mcap_pointer},
                    )
                return SmokeTestResult(
                    passed=False,
                    test_name="foxglove_smoke_test",
                    duration_ms=duration_ms,
                    message=health.message,
                )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="foxglove_smoke_test",
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
        """Export Foxglove integration artifacts including MCAP pointer."""
        artifacts = await super().export_artifacts(context)

        # Generate MCAP bundle pointer
        foxglove_config = self._typed_config.foxglove
        if foxglove_config and foxglove_config.enable_mcap_export:
            mcap_pointer = self.generate_mcap_bundle_pointer(context)
            artifacts.append(ExportArtifact(
                name="foxglove-mcap-pointer.json",
                content=json.dumps(mcap_pointer, indent=2),
                artifact_type="json",
                metadata={
                    "provider": "foxglove",
                    "type": "mcap_bundle_pointer",
                },
            ))

        # Add integration manifest
        manifest = {
            "provider": "foxglove",
            "version": "1.0",
            "capabilities": [c.value for c in self.robotics_capabilities()],
            "outbound": {
                "mode": self._typed_config.outbound.mode.value,
                "event_types": [
                    "candidate_created", "gate_failed", "promoted",
                    "rollback", "route_frozen", "route_unfrozen",
                ],
            },
            "features": {
                "mcap_export_enabled": (
                    foxglove_config.enable_mcap_export
                    if foxglove_config else False
                ),
            },
            "context": {
                "route_key": context.get("route_key"),
                "run_id": context.get("run_id"),
            },
        }

        artifacts.append(ExportArtifact(
            name="foxglove-integration-manifest.json",
            content=json.dumps(manifest, indent=2),
            artifact_type="json",
            metadata={"provider": "foxglove"},
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
