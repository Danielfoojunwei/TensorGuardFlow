# OPS Signal Model - TensorGuardFlow Robotics Integrations

This document defines the canonical data model for bidirectional communication between TensorGuardFlow and external robotics operations platforms (InOrbit, Formant, Foxglove, and generic providers).

## Overview

TensorGuardFlow acts as the **control plane and trust layer** for continuous PEFT (Parameter-Efficient Fine-Tuning) updates in robotics deployments. The OPS Signal Model defines two canonical schemas:

1. **OutboundOpsEvent**: Events emitted from TensorGuardFlow to robotics ops tools
2. **InboundOpsSignal**: Signals received from robotics ops tools that trigger TensorGuardFlow actions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TensorGuardFlow Core                                │
│  ┌──────────────────┐    ┌────────────────┐    ┌───────────────────────┐   │
│  │ Continual Learn  │───▶│ OpsSignalRouter│───▶│ Release Safety Actions│   │
│  │ Pipeline (PEFT)  │    │                │    │ (rollback/freeze/etc)  │   │
│  └──────────────────┘    └───────┬────────┘    └───────────────────────┘   │
│           │                      │                                          │
│           ▼                      ▼                                          │
│  ┌──────────────────┐    ┌────────────────┐                                │
│  │ OutboundOpsEvent │    │InboundOpsSignal│                                │
│  └────────┬─────────┘    └───────▲────────┘                                │
└───────────┼──────────────────────┼──────────────────────────────────────────┘
            │                      │
            ▼                      │
┌───────────────────────────────────────────────────────────────────────────┐
│                     External Robotics Ops Platforms                        │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌──────────────────┐ │
│  │  InOrbit  │    │  Formant  │    │  Foxglove │    │  Generic Webhook │ │
│  └───────────┘    └───────────┘    └───────────┘    └──────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 1. OutboundOpsEvent Schema

Events emitted from TensorGuardFlow to external robotics operations platforms.

### Schema Definition

```python
class OutboundOpsEvent:
    # Required Fields
    event_id: str           # UUID v4
    ts: str                 # ISO8601 timestamp (e.g., "2026-01-28T12:00:00Z")
    tenant_id: str          # Tenant identifier
    route_key: str          # Route identifier (e.g., "nav-policy-prod")

    # Event Classification
    severity: Severity      # INFO | WARN | CRITICAL
    category: Category      # See below
    type: EventType         # See below

    # Human-Readable Summary
    summary: str            # Max 256 chars

    # Structured Payload
    payload: EventPayload   # Event-specific data
```

### Severity Levels

| Severity | Description | External Platform Mapping |
|----------|-------------|--------------------------|
| `INFO` | Informational events (promotions, candidate creation) | Notification/log |
| `WARN` | Warning events (gate failures, incomplete evidence) | Alert/warning |
| `CRITICAL` | Critical events requiring immediate attention (rollback, quarantine) | Incident/alarm |

### Categories

| Category | Description |
|----------|-------------|
| `CONTINUAL_LEARNING` | PEFT/adapter training lifecycle events |
| `RELEASE` | Release/promotion/rollback events |
| `TRUST` | Signature, attestation, verification events |
| `PRIVACY` | N2HE privacy receipt events |
| `INTEGRATION` | Integration health/connectivity events |
| `RUNTIME` | Runtime/serving events |

### Event Types

| Type | Category | Severity | Description |
|------|----------|----------|-------------|
| `candidate_created` | CONTINUAL_LEARNING | INFO | New adapter candidate created |
| `gate_failed` | CONTINUAL_LEARNING | WARN | Gate evaluation failed |
| `promoted` | RELEASE | INFO | Adapter promoted to production |
| `rollback` | RELEASE | CRITICAL | Rollback executed |
| `route_frozen` | RELEASE | WARN | Route updates frozen |
| `route_unfrozen` | RELEASE | INFO | Route updates resumed |
| `adapter_quarantined` | RELEASE | CRITICAL | Adapter quarantined due to safety issue |
| `resolve_degraded` | RUNTIME | WARN | Runtime resolution degraded |
| `evidence_incomplete` | TRUST | WARN | Evidence chain incomplete |
| `signature_failed` | TRUST | CRITICAL | Signature verification failed |
| `privacy_receipt_failed` | PRIVACY | WARN | Privacy receipt generation/validation failed |

### Payload Structure

```python
class EventPayload:
    # Adapter Context (optional)
    adapter_id: Optional[str]           # e.g., "adpt_abc123"
    run_id: Optional[str]               # e.g., "run-20260128-001"
    base_model: Optional[str]           # e.g., "meta-llama/Llama-3.1-8B"

    # Metrics Snapshot (optional)
    metrics_snapshot: Optional[dict]    # Current metrics at event time
    # Example: {"accuracy": 0.92, "latency_p99_ms": 45, "safety_score": 0.98}

    # Evidence References (optional)
    evidence_refs: Optional[EvidenceRefs]

    # Integration Topology (optional)
    integration_topology_fingerprint: Optional[str]  # sha256 hash of topology

    # Action Context (optional, for rollback/freeze events)
    action_context: Optional[ActionContext]

    # Extended Fields (provider-specific)
    extended: Optional[dict]

class EvidenceRefs:
    tgsp_uri: Optional[str]     # URI to TGSP package
    evidence_uri: Optional[str]  # URI to evidence bundle
    policy_hash: Optional[str]   # Hash of policy used

class ActionContext:
    triggered_by: str           # "auto" | "manual" | "ops_signal"
    reason: str                 # Human-readable reason
    previous_adapter_id: Optional[str]
    rollback_target_adapter_id: Optional[str]
    signal_id: Optional[str]    # If triggered by inbound signal
```

### Example OutboundOpsEvent

```json
{
  "event_id": "evt_01J8K9M2N3P4Q5R6S7T8U9V0",
  "ts": "2026-01-28T14:30:00.000Z",
  "tenant_id": "tenant_robotics_corp",
  "route_key": "nav-policy-prod",
  "severity": "CRITICAL",
  "category": "RELEASE",
  "type": "rollback",
  "summary": "Automatic rollback triggered due to safety regression detected by InOrbit",
  "payload": {
    "adapter_id": "adpt_failed_123",
    "run_id": "run-20260128-042",
    "metrics_snapshot": {
      "safety_score": 0.72,
      "collision_near_miss_rate": 0.05,
      "latency_p99_ms": 120
    },
    "evidence_refs": {
      "tgsp_uri": "tgsp://tenant_robotics_corp/nav-policy-prod/run-20260128-042.tgsp",
      "evidence_uri": "s3://evidence-bucket/nav-policy-prod/run-20260128-042/evidence.json"
    },
    "action_context": {
      "triggered_by": "ops_signal",
      "reason": "Safety regression detected: collision near-miss rate exceeded threshold",
      "previous_adapter_id": "adpt_failed_123",
      "rollback_target_adapter_id": "adpt_stable_122",
      "signal_id": "sig_inorbit_abc123"
    }
  }
}
```

---

## 2. InboundOpsSignal Schema

Signals received from external robotics operations platforms that may trigger TensorGuardFlow actions.

### Schema Definition

```python
class InboundOpsSignal:
    # Required Fields
    signal_id: str          # UUID v4 (generated by TGF upon receipt)
    ts: str                 # ISO8601 timestamp of signal receipt

    # Source Identification
    source: SignalSource    # INORBIT | FORMANT | FOXGLOVE | GENERIC

    # Tenant & Route Targeting
    tenant_id: Optional[str]        # Explicit tenant ID
    tenant_hint: Optional[str]      # Hint for tenant lookup (e.g., robot ID)
    route_key: str                  # Required: target route

    # Signal Classification
    severity: Severity      # WARN | CRITICAL
    type: SignalType        # See below

    # Payload
    payload: SignalPayload  # Raw + normalized fields

    # Authentication
    auth: AuthInfo          # Signature verification status

    # Replay Protection
    dedupe_key: str         # Unique key for deduplication

    # Processing Status
    received_at: str        # ISO8601 timestamp
    processed_at: Optional[str]
    action_taken: Optional[str]
```

### Signal Sources

| Source | Description |
|--------|-------------|
| `INORBIT` | InOrbit fleet management platform |
| `FORMANT` | Formant robotics platform |
| `FOXGLOVE` | Foxglove observability platform |
| `GENERIC` | Generic webhook source |

### Signal Types

| Type | Description | Recommended Action |
|------|-------------|-------------------|
| `incident` | Generic incident reported | Investigate, may freeze |
| `regression_detected` | Performance regression detected | Evaluate rollback |
| `drift_detected` | Model/behavior drift detected | Investigate, may rollback |
| `safety_stop` | Safety system triggered | Immediate freeze/quarantine |
| `task_failure_spike` | Sudden increase in task failures | Evaluate rollback |
| `latency_spike` | Latency exceeded threshold | Investigate, may rollback |
| `manual_rollback_request` | Operator requested rollback | Execute rollback |
| `freeze_request` | Operator requested freeze | Execute freeze |

### Payload Structure

```python
class SignalPayload:
    # Raw payload from source (preserved for audit)
    raw: dict

    # Normalized fields (extracted by connector)
    normalized: NormalizedSignalData

class NormalizedSignalData:
    # Metrics at signal time (optional)
    metrics: Optional[dict]

    # Affected robots/agents (optional)
    affected_agents: Optional[List[str]]

    # Threshold violation details (optional)
    threshold_violation: Optional[ThresholdViolation]

    # Operator notes (optional)
    operator_notes: Optional[str]

    # Suggested action (optional, from source platform)
    suggested_action: Optional[str]

class ThresholdViolation:
    metric_name: str
    current_value: float
    threshold_value: float
    direction: str  # "above" | "below"
```

### Authentication Info

```python
class AuthInfo:
    signature_present: bool
    verified: bool
    key_id: Optional[str]
    verification_error: Optional[str]
```

### Example InboundOpsSignal

```json
{
  "signal_id": "sig_01J8K9M2N3P4Q5R6S7T8U9V0",
  "ts": "2026-01-28T14:29:55.000Z",
  "source": "INORBIT",
  "tenant_id": "tenant_robotics_corp",
  "route_key": "nav-policy-prod",
  "severity": "CRITICAL",
  "type": "safety_stop",
  "payload": {
    "raw": {
      "event_type": "robot.safety.triggered",
      "robot_id": "robot-alpha-001",
      "reason": "Emergency stop triggered by proximity sensor",
      "timestamp": 1738073395000
    },
    "normalized": {
      "affected_agents": ["robot-alpha-001"],
      "metrics": {
        "collision_near_miss_count": 3,
        "proximity_alert_count": 12
      },
      "threshold_violation": {
        "metric_name": "collision_near_miss_rate",
        "current_value": 0.05,
        "threshold_value": 0.01,
        "direction": "above"
      },
      "operator_notes": "Emergency stop triggered during autonomous navigation"
    }
  },
  "auth": {
    "signature_present": true,
    "verified": true,
    "key_id": "inorbit-webhook-key-2026"
  },
  "dedupe_key": "inorbit:robot-alpha-001:safety_stop:1738073395",
  "received_at": "2026-01-28T14:29:55.100Z"
}
```

---

## 3. Signal-to-Action Mapping

The OpsSignalRouter maps inbound signals to TensorGuardFlow actions based on signal type, severity, and route policy.

### Action Types

| Action | Description | Requirements |
|--------|-------------|--------------|
| `rollback_route` | Rollback route to previous stable adapter | `allow_auto_rollback=true` on route |
| `freeze_route` | Freeze route updates (no new promotions) | `allow_auto_freeze=true` on route |
| `quarantine_adapter` | Quarantine specific adapter | Any signal with `severity=CRITICAL` |
| `open_investigation` | Create investigation event for review | Default for `severity=WARN` |
| `acknowledge` | Acknowledge signal, no action | Manual acknowledgment |

### Policy Configuration (per Route)

```yaml
route_policy:
  route_key: "nav-policy-prod"

  ops_signal_policy:
    # Automation Controls
    allow_auto_rollback: true
    allow_auto_freeze: true
    require_verified_signature_for_automation: true

    # Thresholds
    cooldown_window_sec: 300  # Prevent thrashing
    max_auto_actions_per_hour: 5

    # Signal Type Overrides
    signal_type_actions:
      safety_stop: "quarantine_adapter"
      regression_detected: "rollback_route"
      latency_spike: "open_investigation"
      manual_rollback_request: "rollback_route"
      freeze_request: "freeze_route"
```

### Decision Flow

```
Inbound Signal Received
        │
        ▼
┌───────────────────┐
│ Verify Signature  │──────[FAIL]───▶ Reject (if required)
│ (if configured)   │
└───────┬───────────┘
        │[PASS]
        ▼
┌───────────────────┐
│ Replay Protection │──────[DUPLICATE]───▶ Ignore
│ (dedupe_key check)│
└───────┬───────────┘
        │[NEW]
        ▼
┌───────────────────┐
│ Lookup Route      │──────[NOT FOUND]───▶ Log warning, no action
│ Policy            │
└───────┬───────────┘
        │[FOUND]
        ▼
┌───────────────────┐
│ Check Cooldown    │──────[COOLDOWN]───▶ Queue for later
└───────┬───────────┘
        │[READY]
        ▼
┌───────────────────┐
│ Map Signal Type   │
│ to Action         │
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ Execute Action    │──────▶ Emit OutboundOpsEvent confirming action
└───────────────────┘
```

---

## 4. Security Considerations

### Signature Verification

All connectors support webhook signature verification:

- **HMAC-SHA256**: Shared secret signed request body
- **RSA/ECDSA**: Public key verification (provider-specific)

```python
# HMAC verification
signature = hmac.new(
    secret.encode(),
    request_body,
    hashlib.sha256
).hexdigest()

# Constant-time comparison (required)
if not hmac.compare_digest(signature, received_signature):
    raise SignatureVerificationError()
```

### Replay Protection

- **Time Window**: Reject signals with timestamp outside acceptable window (default: 5 minutes)
- **Dedupe Key**: Cache recent dedupe_keys to reject replays
- **Cache Size**: Bounded cache (default: 10,000 keys)

```python
dedupe_cache = BoundedCache(max_size=10000, ttl_sec=300)

def is_replay(signal: InboundOpsSignal) -> bool:
    if abs(time.time() - parse_iso(signal.ts)) > WINDOW_SEC:
        return True  # Too old
    if signal.dedupe_key in dedupe_cache:
        return True  # Already processed
    dedupe_cache.add(signal.dedupe_key)
    return False
```

### Safe Logging

- **Never** log raw webhook payloads in production
- **Redact** all secret values, tokens, API keys
- **N2HE Compliance**: When N2HE mode is enabled, ensure no plaintext identifiers appear in logs

---

## 5. Dead Letter Queue (DLQ)

Failed outbound event deliveries are persisted for retry:

```python
class OutboundEventDLQ:
    event_id: str
    event_payload: str  # JSON serialized
    target_provider: str
    target_url: str
    failure_reason: str
    retry_count: int
    next_retry_at: datetime
    created_at: datetime
```

Retry policy:
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 64s, 128s, 256s, 512s
- Max retries: 10
- After max retries: Mark as permanently failed, alert operators

---

## 6. Integration Topology

The robotics integrations appear as nodes in the TensorGuardFlow integration topology:

```
Category F/G Extended:
┌─────────────────────────────────────────────────────────────┐
│                    Robotics Ops Nodes                        │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐           │
│  │  InOrbit  │    │  Formant  │    │  Foxglove │           │
│  │  (F/G)    │    │  (F/G)    │    │  (F/G)    │           │
│  └─────┬─────┘    └─────┬─────┘    └─────┬─────┘           │
│        │                │                │                  │
│        └────────────────┼────────────────┘                  │
│                         ▼                                   │
│              ┌────────────────────┐                         │
│              │  OpsSignalRouter   │                         │
│              │  (Central Hub)     │                         │
│              └──────────┬─────────┘                         │
│                         │                                   │
│                         ▼                                   │
│              ┌────────────────────┐                         │
│              │  Release Safety    │                         │
│              │  (Route Manager)   │                         │
│              └────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Versioning

- Current Schema Version: `1.0`
- Backward Compatibility: All fields added after v1.0 must be optional
- Version Header: All outbound events include `X-TGF-OpsEvent-Version: 1.0`

---

## Appendix A: Provider-Specific Notes

### InOrbit
- Webhook signature: HMAC-SHA256 in `X-InOrbit-Signature` header
- Dedupe key: `{event_type}:{robot_id}:{timestamp_ms}`
- Rate limit: Respect `X-RateLimit-*` headers

### Formant
- Webhook signature: HMAC-SHA256 in `X-Formant-Signature` header
- Dedupe key: `{event_id}` from payload
- Supports acknowledgment callbacks

### Foxglove
- Typically visualization/recording sink (outbound focus)
- MCAP bundle pointer export for artifact linking
- Webhook signature: Configurable (generic)

---

## Appendix B: Metric Categories for Threshold Monitoring

| Category | Example Metrics |
|----------|-----------------|
| Safety | `collision_near_miss_rate`, `safety_stop_count`, `human_proximity_violations` |
| Performance | `task_success_rate`, `latency_p99_ms`, `throughput_tasks_per_hour` |
| Quality | `accuracy`, `precision`, `recall`, `f1_score` |
| Resource | `memory_usage_percent`, `cpu_usage_percent`, `gpu_utilization` |
| Reliability | `uptime_percent`, `error_rate`, `crash_count` |
