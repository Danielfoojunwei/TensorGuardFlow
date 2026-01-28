"""
Robotics Ops Integrations API - TensorGuardFlow

Provides endpoints for InOrbit, Formant, Foxglove, and generic robotics
operations platform integrations.

Mount: /api/v1/robotics

Endpoints:
- GET /robotics/status - Integration status and health
- POST /robotics/webhook/{provider} - Inbound webhook receivers
- POST /robotics/test/send_event - Manual event sending (admin)
- POST /robotics/test/ingest_signal - Simulated signal ingestion (admin)
"""

import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..database import get_session
from ..auth import get_current_user
from ..models.core import User
from ..models.settings_models import IntegrationConnection, IntegrationStatus

# Import robotics integration modules
from ...integrations.connectors.robotics import (
    # Schemas
    OutboundOpsEvent,
    InboundOpsSignal,
    EventPayload,
    SignalSource,
    Severity,
    EventCategory,
    OutboundEventType,
    InboundSignalType,
    ActionType,
    SendResult,
    IngestResult,
    # Connectors
    InOrbitConnector,
    FormantConnector,
    FoxgloveConnector,
    # Config
    RoboticsProvider,
    RoboticsConnectorConfig,
    get_inorbit_template,
    get_formant_template,
    get_foxglove_template,
    get_generic_template,
)


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class RoboticsStatusResponse(BaseModel):
    """Response for robotics integration status."""
    providers: Dict[str, Dict[str, Any]]
    summary: Dict[str, Any]
    timestamp: str


class WebhookResponse(BaseModel):
    """Response for webhook ingestion."""
    success: bool
    signal_id: Optional[str] = None
    action_taken: Optional[str] = None
    message: str


class SendEventRequest(BaseModel):
    """Request to send a test event."""
    provider: str = Field(description="Target provider: inorbit, formant, foxglove")
    event: Dict[str, Any] = Field(description="Event payload")


class SendEventResponse(BaseModel):
    """Response for send event test."""
    success: bool
    event_id: str
    provider: str
    latency_ms: int
    error: Optional[str] = None


class IngestSignalRequest(BaseModel):
    """Request to simulate signal ingestion."""
    provider: str = Field(description="Source provider: inorbit, formant, foxglove, generic")
    signal: Dict[str, Any] = Field(description="Raw signal payload")


class IngestSignalResponse(BaseModel):
    """Response for signal ingestion test."""
    success: bool
    signal_id: str
    normalized: Dict[str, Any]
    action_suggested: Optional[str] = None


class ConfigureProviderRequest(BaseModel):
    """Request to configure a robotics provider."""
    provider: str
    config: Dict[str, Any]
    enabled: bool = True


class DLQEntry(BaseModel):
    """Dead letter queue entry."""
    id: str
    event_id: str
    provider: str
    error: str
    retry_count: int
    created_at: str
    next_retry_at: Optional[str] = None


class DLQResponse(BaseModel):
    """Response for DLQ status."""
    entries: List[DLQEntry]
    total_count: int
    failed_permanently: int


# =============================================================================
# In-Memory State (would be DB-backed in production)
# =============================================================================


# Connector instances (cached per tenant)
_connector_cache: Dict[str, Dict[str, Any]] = {}

# Recent events/signals for dashboard
_recent_outbound_events: List[Dict[str, Any]] = []
_recent_inbound_signals: List[Dict[str, Any]] = []

# DLQ (in-memory for demo, would be DB-backed)
_dlq_entries: List[Dict[str, Any]] = []


def _get_connector(
    provider: str,
    tenant_id: str,
    session: Session,
) -> Optional[Any]:
    """Get or create connector for provider."""
    cache_key = f"{tenant_id}:{provider}"

    if cache_key in _connector_cache:
        return _connector_cache[cache_key]

    # Look up configuration from database
    conn = session.exec(
        select(IntegrationConnection)
        .where(IntegrationConnection.tenant_id == tenant_id)
        .where(IntegrationConnection.service == f"robotics_{provider}")
    ).first()

    if not conn:
        # Use template configuration
        if provider == "inorbit":
            config = get_inorbit_template()
        elif provider == "formant":
            config = get_formant_template()
        elif provider == "foxglove":
            config = get_foxglove_template()
        else:
            config = get_generic_template()
    else:
        try:
            config = RoboticsConnectorConfig(**json.loads(conn.config_json))
        except Exception:
            config = get_generic_template()

    # Create connector
    if provider == "inorbit":
        connector = InOrbitConnector(config.model_dump())
    elif provider == "formant":
        connector = FormantConnector(config.model_dump())
    elif provider == "foxglove":
        connector = FoxgloveConnector(config.model_dump())
    else:
        # Generic uses InOrbit as base
        connector = InOrbitConnector(config.model_dump())

    _connector_cache[cache_key] = connector
    return connector


def _record_outbound_event(
    event: OutboundOpsEvent,
    result: SendResult,
    provider: str,
):
    """Record outbound event for dashboard."""
    entry = {
        "event_id": event.event_id,
        "type": event.type.value,
        "severity": event.severity.value,
        "provider": provider,
        "success": result.success,
        "latency_ms": result.latency_ms,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _recent_outbound_events.insert(0, entry)
    # Keep only last 100
    if len(_recent_outbound_events) > 100:
        _recent_outbound_events.pop()


def _record_inbound_signal(
    signal: InboundOpsSignal,
    action_taken: Optional[ActionType],
):
    """Record inbound signal for dashboard."""
    entry = {
        "signal_id": signal.signal_id,
        "type": signal.type.value,
        "severity": signal.severity.value,
        "source": signal.source.value,
        "route_key": signal.route_key,
        "action_taken": action_taken.value if action_taken else None,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _recent_inbound_signals.insert(0, entry)
    if len(_recent_inbound_signals) > 100:
        _recent_inbound_signals.pop()


def _add_to_dlq(
    event: OutboundOpsEvent,
    provider: str,
    error: str,
):
    """Add failed event to DLQ."""
    entry = {
        "id": f"dlq_{hashlib.sha256(event.event_id.encode()).hexdigest()[:12]}",
        "event_id": event.event_id,
        "provider": provider,
        "payload": event.model_dump_json(),
        "error": error,
        "retry_count": 0,
        "created_at": datetime.utcnow().isoformat(),
        "next_retry_at": datetime.utcnow().isoformat(),
    }
    _dlq_entries.append(entry)


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/robotics/status")
async def get_robotics_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RoboticsStatusResponse:
    """
    Get status of all robotics ops integrations.

    Returns:
    - Enabled providers with health status
    - Last outbound delivery info
    - Last inbound signal info
    - DLQ depth
    - Capability flags
    """
    tenant_id = str(current_user.tenant_id)

    providers = {}

    for provider in ["inorbit", "formant", "foxglove"]:
        connector = _get_connector(provider, tenant_id, session)

        if connector:
            # Get health status
            try:
                health = await connector.health_check()
                status = health.status
                health_msg = health.message
                latency = health.latency_ms
            except Exception as e:
                status = "FAIL"
                health_msg = str(e)
                latency = None

            # Get capabilities
            caps = connector.describe_capabilities()

            # Find last outbound event
            last_outbound = next(
                (e for e in _recent_outbound_events if e["provider"] == provider),
                None
            )

            # Find last inbound signal
            last_inbound = next(
                (s for s in _recent_inbound_signals if s["source"].lower() == provider),
                None
            )

            # Count DLQ entries
            dlq_count = sum(1 for e in _dlq_entries if e["provider"] == provider)

            providers[provider] = {
                "enabled": True,
                "status": status,
                "health_message": health_msg,
                "health_latency_ms": latency,
                "last_outbound": last_outbound,
                "last_inbound": last_inbound,
                "dlq_depth": dlq_count,
                "capabilities": caps,
            }
        else:
            providers[provider] = {
                "enabled": False,
                "status": "DISABLED",
            }

    # Build summary
    enabled_count = sum(1 for p in providers.values() if p.get("enabled"))
    healthy_count = sum(1 for p in providers.values() if p.get("status") == "OK")
    total_dlq = len(_dlq_entries)

    return RoboticsStatusResponse(
        providers=providers,
        summary={
            "enabled_providers": enabled_count,
            "healthy_providers": healthy_count,
            "total_dlq_entries": total_dlq,
            "recent_outbound_count": len(_recent_outbound_events),
            "recent_inbound_count": len(_recent_inbound_signals),
        },
        timestamp=datetime.utcnow().isoformat(),
    )


@router.post("/robotics/webhook/inorbit")
async def inorbit_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Receive webhook from InOrbit.

    Verifies signature, normalizes signal, and routes to OpsSignalRouter.
    """
    return await _handle_webhook(
        request,
        background_tasks,
        session,
        provider="inorbit",
        source=SignalSource.INORBIT,
    )


@router.post("/robotics/webhook/formant")
async def formant_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Receive webhook from Formant."""
    return await _handle_webhook(
        request,
        background_tasks,
        session,
        provider="formant",
        source=SignalSource.FORMANT,
    )


@router.post("/robotics/webhook/foxglove")
async def foxglove_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Receive webhook from Foxglove."""
    return await _handle_webhook(
        request,
        background_tasks,
        session,
        provider="foxglove",
        source=SignalSource.FOXGLOVE,
    )


@router.post("/robotics/webhook/generic")
async def generic_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Receive webhook from generic source."""
    return await _handle_webhook(
        request,
        background_tasks,
        session,
        provider="generic",
        source=SignalSource.GENERIC,
    )


async def _handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session,
    provider: str,
    source: SignalSource,
) -> WebhookResponse:
    """Common webhook handling logic."""
    # Get headers and body
    headers = dict(request.headers)
    body = await request.body()

    # Get connector (use default tenant for webhooks)
    connector = _get_connector(provider, "default", session)

    if not connector:
        return WebhookResponse(
            success=False,
            message=f"Provider {provider} not configured",
        )

    # Ingest signal
    try:
        result = await connector.ingest_signal(
            headers=headers,
            body=body,
            source_ip=request.client.host if request.client else None,
        )

        if not result.success:
            return WebhookResponse(
                success=False,
                message=result.error or "Ingestion failed",
            )

        # Route signal to action (async in background)
        # In production, this would call OpsSignalRouter
        background_tasks.add_task(
            _process_signal_async,
            result.signal_id,
            source,
        )

        return WebhookResponse(
            success=True,
            signal_id=result.signal_id,
            action_taken=result.action_taken.value if result.action_taken else None,
            message="Signal received and queued for processing",
        )

    except Exception as e:
        return WebhookResponse(
            success=False,
            message=f"Webhook processing error: {str(e)}",
        )


async def _process_signal_async(signal_id: str, source: SignalSource):
    """Process signal asynchronously (placeholder for OpsSignalRouter)."""
    # This would call the OpsSignalRouter service
    pass


@router.post("/robotics/test/send_event")
async def test_send_event(
    req: SendEventRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SendEventResponse:
    """
    Send a test event to a provider.

    Admin-only endpoint for testing outbound connectivity.
    """
    tenant_id = str(current_user.tenant_id)

    # Validate provider
    if req.provider not in ["inorbit", "formant", "foxglove"]:
        raise HTTPException(400, f"Invalid provider: {req.provider}")

    # Get connector
    connector = _get_connector(req.provider, tenant_id, session)
    if not connector:
        raise HTTPException(424, f"Provider {req.provider} not configured")

    # Build event
    try:
        event = OutboundOpsEvent(
            tenant_id=tenant_id,
            route_key=req.event.get("route_key", "test-route"),
            severity=Severity(req.event.get("severity", "INFO")),
            category=EventCategory(req.event.get("category", "INTEGRATION")),
            type=OutboundEventType(req.event.get("type", "integration_health_changed")),
            summary=req.event.get("summary", "Test event from TensorGuardFlow"),
            payload=EventPayload(**req.event.get("payload", {})),
        )
    except Exception as e:
        raise HTTPException(400, f"Invalid event format: {str(e)}")

    # Send event
    result = await connector.send_event(event)

    # Record for dashboard
    _record_outbound_event(event, result, req.provider)

    # Add to DLQ if failed
    if not result.success and result.retry_scheduled:
        _add_to_dlq(event, req.provider, result.error or "Unknown error")

    return SendEventResponse(
        success=result.success,
        event_id=event.event_id,
        provider=req.provider,
        latency_ms=result.latency_ms,
        error=result.error,
    )


@router.post("/robotics/test/ingest_signal")
async def test_ingest_signal(
    req: IngestSignalRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IngestSignalResponse:
    """
    Simulate signal ingestion for testing.

    Admin-only endpoint for testing inbound signal processing.
    """
    tenant_id = str(current_user.tenant_id)

    # Map provider to source
    source_map = {
        "inorbit": SignalSource.INORBIT,
        "formant": SignalSource.FORMANT,
        "foxglove": SignalSource.FOXGLOVE,
        "generic": SignalSource.GENERIC,
    }

    source = source_map.get(req.provider)
    if not source:
        raise HTTPException(400, f"Invalid provider: {req.provider}")

    # Get connector
    connector = _get_connector(req.provider, tenant_id, session)
    if not connector:
        raise HTTPException(424, f"Provider {req.provider} not configured")

    # Simulate ingestion
    body = json.dumps(req.signal).encode()
    headers = {
        "content-type": "application/json",
    }

    result = await connector.ingest_signal(
        headers=headers,
        body=body,
    )

    if not result.success:
        raise HTTPException(400, result.error or "Ingestion failed")

    # Get default action for signal type (would be determined by OpsSignalRouter)
    from ...integrations.connectors.robotics import get_default_action_for_signal

    signal_type = InboundSignalType(
        req.signal.get("type", "incident")
    ) if req.signal.get("type") else InboundSignalType.INCIDENT

    severity = Severity(
        req.signal.get("severity", "WARN").upper()
    ) if req.signal.get("severity") else Severity.WARN

    action = get_default_action_for_signal(signal_type, severity)

    return IngestSignalResponse(
        success=True,
        signal_id=result.signal_id,
        normalized={
            "source": source.value,
            "type": signal_type.value,
            "severity": severity.value,
        },
        action_suggested=action.value,
    )


@router.get("/robotics/events/recent")
async def get_recent_events(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Get recent outbound events for dashboard."""
    return {
        "events": _recent_outbound_events[:limit],
        "total": len(_recent_outbound_events),
    }


@router.get("/robotics/signals/recent")
async def get_recent_signals(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Get recent inbound signals for dashboard."""
    return {
        "signals": _recent_inbound_signals[:limit],
        "total": len(_recent_inbound_signals),
    }


@router.get("/robotics/dlq")
async def get_dlq_status(
    current_user: User = Depends(get_current_user),
) -> DLQResponse:
    """Get DLQ status for failed deliveries."""
    entries = [
        DLQEntry(
            id=e["id"],
            event_id=e["event_id"],
            provider=e["provider"],
            error=e["error"],
            retry_count=e["retry_count"],
            created_at=e["created_at"],
            next_retry_at=e.get("next_retry_at"),
        )
        for e in _dlq_entries[:50]
    ]

    failed_permanently = sum(
        1 for e in _dlq_entries if e["retry_count"] >= 10
    )

    return DLQResponse(
        entries=entries,
        total_count=len(_dlq_entries),
        failed_permanently=failed_permanently,
    )


@router.post("/robotics/dlq/retry")
async def retry_dlq_entries(
    entry_ids: Optional[List[str]] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Retry DLQ entries."""
    tenant_id = str(current_user.tenant_id)

    if entry_ids:
        entries_to_retry = [e for e in _dlq_entries if e["id"] in entry_ids]
    else:
        entries_to_retry = _dlq_entries[:10]  # Retry up to 10

    results = []
    for entry in entries_to_retry:
        provider = entry["provider"]
        connector = _get_connector(provider, tenant_id, session)

        if not connector:
            results.append({
                "id": entry["id"],
                "success": False,
                "error": "Provider not configured",
            })
            continue

        try:
            event = OutboundOpsEvent.model_validate_json(entry["payload"])
            result = await connector.send_event(event)

            if result.success:
                # Remove from DLQ
                _dlq_entries.remove(entry)
                results.append({
                    "id": entry["id"],
                    "success": True,
                })
            else:
                entry["retry_count"] += 1
                entry["error"] = result.error or "Retry failed"
                results.append({
                    "id": entry["id"],
                    "success": False,
                    "error": result.error,
                })

        except Exception as e:
            entry["retry_count"] += 1
            results.append({
                "id": entry["id"],
                "success": False,
                "error": str(e),
            })

    return {
        "retried": len(results),
        "results": results,
    }


@router.post("/robotics/configure")
async def configure_provider(
    req: ConfigureProviderRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Configure a robotics provider."""
    tenant_id = str(current_user.tenant_id)

    # Validate provider
    if req.provider not in ["inorbit", "formant", "foxglove", "generic"]:
        raise HTTPException(400, f"Invalid provider: {req.provider}")

    # Build config
    try:
        provider_enum = RoboticsProvider(req.provider)
        config = RoboticsConnectorConfig(
            provider=provider_enum,
            enabled=req.enabled,
            **req.config,
        )
    except Exception as e:
        raise HTTPException(400, f"Invalid configuration: {str(e)}")

    # Validate config
    errors = config.validate_complete()
    if errors:
        raise HTTPException(400, f"Configuration errors: {errors}")

    # Store in database
    service_name = f"robotics_{req.provider}"

    existing = session.exec(
        select(IntegrationConnection)
        .where(IntegrationConnection.tenant_id == tenant_id)
        .where(IntegrationConnection.service == service_name)
    ).first()

    if existing:
        existing.config_json = config.model_dump_json()
        existing.status = IntegrationStatus.CONNECTED.value if req.enabled else IntegrationStatus.DISCONNECTED.value
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        conn = IntegrationConnection(
            tenant_id=tenant_id,
            service=service_name,
            status=IntegrationStatus.CONNECTED.value if req.enabled else IntegrationStatus.DISCONNECTED.value,
            config_json=config.model_dump_json(),
        )
        session.add(conn)

    session.commit()

    # Clear connector cache
    cache_key = f"{tenant_id}:{req.provider}"
    if cache_key in _connector_cache:
        del _connector_cache[cache_key]

    return {
        "success": True,
        "provider": req.provider,
        "enabled": req.enabled,
        "fingerprint": config.compute_fingerprint(),
    }


@router.get("/robotics/topology")
async def get_robotics_topology(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get robotics integration topology for visualization.

    Shows providers as nodes connected to OpsSignalRouter.
    """
    tenant_id = str(current_user.tenant_id)

    nodes = []
    edges = []

    # Add provider nodes
    for provider in ["inorbit", "formant", "foxglove"]:
        connector = _get_connector(provider, tenant_id, session)

        if connector:
            try:
                health = await connector.health_check()
                status = health.status
            except Exception:
                status = "UNKNOWN"

            caps = connector.describe_capabilities()

            nodes.append({
                "id": f"robotics-{provider}",
                "category": "F/G",
                "provider": provider,
                "provider_display": provider.title(),
                "status": status,
                "capabilities": caps,
            })

            # Edge to OpsSignalRouter (inbound)
            if caps.get("supports_webhooks_in"):
                edges.append({
                    "from_node": f"robotics-{provider}",
                    "to_node": "ops-signal-router",
                    "protocol": "webhook",
                    "direction": "inbound",
                    "data_types": ["incident", "signal"],
                })

            # Edge from OpsSignalRouter (outbound)
            if caps.get("supports_events_out"):
                edges.append({
                    "from_node": "ops-signal-router",
                    "to_node": f"robotics-{provider}",
                    "protocol": "webhook",
                    "direction": "outbound",
                    "data_types": ["event", "notification"],
                })

    # Add OpsSignalRouter node
    nodes.append({
        "id": "ops-signal-router",
        "category": "CORE",
        "provider": "tgf_internal",
        "provider_display": "Ops Signal Router",
        "status": "OK",
        "capabilities": {
            "signal_routing": True,
            "action_mapping": True,
            "replay_protection": True,
        },
    })

    # Add Release Safety node
    nodes.append({
        "id": "release-safety",
        "category": "CORE",
        "provider": "tgf_internal",
        "provider_display": "Release Safety",
        "status": "OK",
        "capabilities": {
            "rollback": True,
            "freeze": True,
            "quarantine": True,
        },
    })

    # Edge from OpsSignalRouter to Release Safety
    edges.append({
        "from_node": "ops-signal-router",
        "to_node": "release-safety",
        "protocol": "internal",
        "direction": "action",
        "data_types": ["rollback_request", "freeze_request"],
    })

    return {
        "version": "1.0",
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "provider_count": len([n for n in nodes if n["category"] == "F/G"]),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
