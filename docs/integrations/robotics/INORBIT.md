# InOrbit Integration Guide

TensorGuardFlow integration with [InOrbit](https://www.inorbit.ai/) for robotics fleet management and operations.

## Overview

InOrbit is a cloud-based robot operations platform that provides fleet management, real-time monitoring, and incident management. TensorGuardFlow integrates with InOrbit to:

- **Outbound**: Push PEFT deployment events, drift alerts, and model health metrics to InOrbit dashboards
- **Inbound**: Receive incident signals, anomaly detections, and operator actions to trigger TensorGuardFlow responses (rollback, freeze, quarantine)

## Architecture

```
┌─────────────────────┐          ┌─────────────────────┐
│   TensorGuardFlow   │          │       InOrbit       │
│                     │          │                     │
│  ┌───────────────┐  │  Events  │  ┌───────────────┐  │
│  │ InOrbit       │──┼─────────>│  │ Custom        │  │
│  │ Connector     │  │          │  │ Metrics/Logs  │  │
│  │               │<─┼──────────│  │               │  │
│  └───────────────┘  │ Webhooks │  │ Incident      │  │
│                     │          │  │ Webhooks      │  │
└─────────────────────┘          └─────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Required
INORBIT_API_KEY=your_api_key_here
INORBIT_ACCOUNT_ID=your_account_id

# Optional
INORBIT_API_URL=https://api.inorbit.ai  # Default
INORBIT_WEBHOOK_SECRET=your_webhook_secret  # For signature verification
```

### Connector Configuration

```python
from tensorguard.integrations.connectors.robotics.config import get_inorbit_template

# Get default configuration template
config = get_inorbit_template()

# Customize as needed
config.outbound.enabled = True
config.outbound.event_types = [
    "peft_deployment_started",
    "peft_deployment_completed",
    "drift_detected",
    "rollback_initiated"
]

config.inbound.enabled = True
config.inbound.require_signature = True  # Recommended for production
config.inbound.signature_header = "X-InOrbit-Signature"
```

### Full Configuration Example

```yaml
# config/robotics/inorbit.yaml
provider: inorbit
enabled: true

outbound:
  enabled: true
  endpoint: https://api.inorbit.ai/v1/custom-data
  event_types:
    - peft_deployment_started
    - peft_deployment_completed
    - peft_deployment_failed
    - drift_detected
    - drift_resolved
    - model_health_degraded
    - rollback_initiated
    - rollback_completed
  batch_size: 10
  flush_interval_seconds: 30
  retry_policy:
    max_retries: 3
    backoff_base_seconds: 2
    backoff_max_seconds: 60

inbound:
  enabled: true
  webhook_path: /api/v1/robotics/webhook/inorbit
  require_signature: true
  signature_header: X-InOrbit-Signature
  timestamp_tolerance_seconds: 300
  allowed_signal_types:
    - incident_created
    - incident_escalated
    - anomaly_detected
    - operator_action

replay_protection:
  enabled: true
  cache_size: 10000
  ttl_seconds: 3600

n2he_privacy:
  enabled: true
  redact_robot_ids: true
  redact_location_data: true
```

## Outbound Events

### Event Types

| Event Type | Description | InOrbit Mapping |
|------------|-------------|-----------------|
| `peft_deployment_started` | PEFT update deployment initiated | Custom metric + log |
| `peft_deployment_completed` | PEFT update successfully deployed | Custom metric + log |
| `peft_deployment_failed` | PEFT update deployment failed | Alert + log |
| `drift_detected` | Model drift detected | Alert |
| `model_health_degraded` | Model performance degradation | Alert |
| `rollback_initiated` | Model rollback started | Alert + log |

### Event Payload Format

TensorGuardFlow events are transformed to InOrbit's custom data format:

```json
{
  "robotId": "fleet-robot-001",
  "timestamp": "2026-01-28T12:00:00Z",
  "customData": {
    "source": "tensorguardflow",
    "event_type": "peft_deployment_completed",
    "model_id": "model-abc123",
    "adapter_id": "adapter-xyz789",
    "version": "v2.1.0",
    "metrics": {
      "deployment_duration_ms": 1234,
      "validation_score": 0.95
    }
  }
}
```

## Inbound Signals

### Supported Signal Types

| InOrbit Event | TensorGuardFlow Signal | Default Action |
|---------------|------------------------|----------------|
| `incident.created` (Critical) | `critical_incident` | `rollback` |
| `incident.created` (High) | `high_incident` | `freeze_deployment` |
| `incident.escalated` | `escalated_incident` | `rollback` |
| `anomaly.detected` | `anomaly_alert` | `quarantine` |
| `operator.action` | `manual_intervention` | `investigate` |

### Webhook Payload Example

InOrbit sends webhooks in this format:

```json
{
  "event_type": "incident.created",
  "timestamp": "2026-01-28T12:00:00Z",
  "data": {
    "incident_id": "inc-12345",
    "severity": "critical",
    "robot_id": "fleet-robot-001",
    "description": "Model inference latency exceeded threshold",
    "metadata": {
      "latency_ms": 5000,
      "threshold_ms": 1000
    }
  }
}
```

### Signature Verification

InOrbit signs webhooks using HMAC-SHA256. TensorGuardFlow validates signatures:

```
X-InOrbit-Signature: t=1706443200,v1=abc123...
```

The signature is computed as:
```
HMAC-SHA256(webhook_secret, timestamp + "." + request_body)
```

## Security Considerations

### Credential Management

- Store `INORBIT_API_KEY` in your secrets manager (Vault, AWS Secrets Manager, etc.)
- Never log or expose API keys
- Use BYOKMS if available for key rotation

### Webhook Security

1. **Always enable signature verification** in production
2. Set appropriate `timestamp_tolerance_seconds` (default: 300)
3. Enable replay protection to prevent duplicate processing

### N2HE Privacy Mode

When N2HE privacy mode is enabled:
- Robot IDs are hashed before logging
- Location data is redacted
- Only privacy-safe metadata is logged

## Troubleshooting

### Common Issues

**Events not appearing in InOrbit:**
1. Verify `INORBIT_API_KEY` is valid
2. Check outbound endpoint URL
3. Review DLQ for failed deliveries: `GET /api/v1/robotics/dlq`

**Webhook signature verification failing:**
1. Ensure `INORBIT_WEBHOOK_SECRET` matches InOrbit configuration
2. Check timestamp tolerance settings
3. Verify webhook URL is configured correctly in InOrbit

**High latency on event delivery:**
1. Check batch settings (reduce `flush_interval_seconds`)
2. Review retry policy configuration
3. Monitor network connectivity to InOrbit API

### Smoke Test

Run the InOrbit smoke test to verify connectivity:

```bash
# Requires valid credentials
PYTHONPATH=src python -c "
from tensorguard.integrations.connectors.robotics.inorbit_connector import InOrbitConnector
from tensorguard.integrations.connectors.robotics.config import get_inorbit_template

config = get_inorbit_template()
connector = InOrbitConnector(config)
result = connector.smoke_test()
print(f'Smoke test result: {result}')
"
```

## API Reference

### InOrbitConnector

```python
class InOrbitConnector(RoboticsOpsConnector):
    """InOrbit robotics ops platform connector."""

    async def send_event(self, event: OutboundOpsEvent) -> bool:
        """Send event to InOrbit."""

    async def ingest_signal(
        self,
        raw_payload: dict,
        headers: dict | None = None
    ) -> InboundOpsSignal | None:
        """Process incoming InOrbit webhook."""

    def smoke_test(self) -> dict:
        """Test connectivity to InOrbit API."""
```

## Related Documentation

- [OPS Signal Model](./OPS_SIGNAL_MODEL.md)
- [Formant Integration](./FORMANT.md)
- [Foxglove Integration](./FOXGLOVE.md)
