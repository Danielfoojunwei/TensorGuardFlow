# Formant Integration Guide

TensorGuardFlow integration with [Formant](https://formant.io/) for robotics fleet management and telemetry.

## Overview

Formant is a robotics data platform that provides fleet management, telemetry collection, and incident management. TensorGuardFlow integrates with Formant to:

- **Outbound**: Push PEFT deployment events, model metrics, and drift alerts to Formant streams
- **Inbound**: Receive incident signals and operator interventions to trigger TensorGuardFlow responses

## Architecture

```
┌─────────────────────┐          ┌─────────────────────┐
│   TensorGuardFlow   │          │       Formant       │
│                     │          │                     │
│  ┌───────────────┐  │  Events  │  ┌───────────────┐  │
│  │ Formant       │──┼─────────>│  │ Data Streams  │  │
│  │ Connector     │  │          │  │ & Telemetry   │  │
│  │               │<─┼──────────│  │               │  │
│  └───────────────┘  │ Webhooks │  │ Incident      │  │
│                     │          │  │ Alerts        │  │
└─────────────────────┘          └─────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Required
FORMANT_API_TOKEN=your_api_token_here
FORMANT_ORGANIZATION_ID=your_org_id

# Optional
FORMANT_API_URL=https://api.formant.io  # Default
FORMANT_WEBHOOK_SECRET=your_webhook_secret  # For signature verification
```

### Connector Configuration

```python
from tensorguard.integrations.connectors.robotics.config import get_formant_template

# Get default configuration template
config = get_formant_template()

# Customize as needed
config.outbound.enabled = True
config.inbound.enabled = True
config.inbound.require_signature = True
```

### Full Configuration Example

```yaml
# config/robotics/formant.yaml
provider: formant
enabled: true

outbound:
  enabled: true
  endpoint: https://api.formant.io/v1/admin/data
  event_types:
    - peft_deployment_started
    - peft_deployment_completed
    - peft_deployment_failed
    - drift_detected
    - drift_resolved
    - model_health_degraded
    - rollback_initiated
    - rollback_completed
  batch_size: 20
  flush_interval_seconds: 15
  retry_policy:
    max_retries: 3
    backoff_base_seconds: 2
    backoff_max_seconds: 60

inbound:
  enabled: true
  webhook_path: /api/v1/robotics/webhook/formant
  require_signature: true
  signature_header: X-Formant-Signature
  timestamp_tolerance_seconds: 300
  allowed_signal_types:
    - incident_created
    - incident_resolved
    - alert_triggered
    - command_executed

replay_protection:
  enabled: true
  cache_size: 10000
  ttl_seconds: 3600

n2he_privacy:
  enabled: true
  redact_robot_ids: true
  redact_location_data: true

# Formant-specific settings
formant_specific:
  stream_name: tensorguardflow_events
  enable_ack_callback: true
  device_filter: null  # null = all devices
```

## Outbound Events

### Event Types

| Event Type | Description | Formant Mapping |
|------------|-------------|-----------------|
| `peft_deployment_started` | PEFT update deployment initiated | Custom stream event |
| `peft_deployment_completed` | PEFT update successfully deployed | Custom stream event |
| `peft_deployment_failed` | PEFT update deployment failed | Alert trigger |
| `drift_detected` | Model drift detected | Alert trigger |
| `model_health_degraded` | Model performance degradation | Alert trigger |
| `rollback_initiated` | Model rollback started | Custom stream event |

### Event Payload Format

TensorGuardFlow events are transformed to Formant's data format:

```json
{
  "deviceId": "fleet-robot-001",
  "stream": "tensorguardflow_events",
  "timestamp": "2026-01-28T12:00:00Z",
  "type": "json",
  "value": {
    "event_type": "peft_deployment_completed",
    "model_id": "model-abc123",
    "adapter_id": "adapter-xyz789",
    "version": "v2.1.0",
    "metrics": {
      "deployment_duration_ms": 1234,
      "validation_score": 0.95
    },
    "tensorguardflow_event_id": "evt-uuid-123"
  }
}
```

## Inbound Signals

### Supported Signal Types

| Formant Event | TensorGuardFlow Signal | Default Action |
|---------------|------------------------|----------------|
| `incident.created` (Critical) | `critical_incident` | `rollback` |
| `incident.created` (High) | `high_incident` | `freeze_deployment` |
| `alert.triggered` | `alert` | `investigate` |
| `command.executed` (stop) | `manual_intervention` | `freeze_deployment` |

### Webhook Payload Example

Formant sends webhooks in this format:

```json
{
  "type": "incident.created",
  "timestamp": "2026-01-28T12:00:00Z",
  "organization_id": "org-12345",
  "data": {
    "incident_id": "inc-67890",
    "severity": "critical",
    "device_id": "fleet-robot-001",
    "title": "Model inference failure",
    "description": "Consecutive inference failures detected",
    "metadata": {
      "failure_count": 10,
      "last_error": "Timeout exceeded"
    }
  }
}
```

### Incident Acknowledgment

Formant connector supports acknowledging incidents after processing:

```python
# Automatic acknowledgment is enabled by default
config.formant_specific.enable_ack_callback = True
```

When enabled, TensorGuardFlow will call Formant's API to acknowledge the incident after successfully processing the signal.

### Signature Verification

Formant signs webhooks using HMAC-SHA256:

```
X-Formant-Signature: sha256=abc123...
```

The signature is computed as:
```
HMAC-SHA256(webhook_secret, request_body)
```

## Security Considerations

### Credential Management

- Store `FORMANT_API_TOKEN` in your secrets manager
- Never log or expose API tokens
- Use BYOKMS if available for key rotation

### Webhook Security

1. **Always enable signature verification** in production
2. Set appropriate `timestamp_tolerance_seconds` (default: 300)
3. Enable replay protection to prevent duplicate processing

### N2HE Privacy Mode

When N2HE privacy mode is enabled:
- Device IDs are hashed before logging
- Location data is redacted
- Only privacy-safe metadata is logged

## Troubleshooting

### Common Issues

**Events not appearing in Formant:**
1. Verify `FORMANT_API_TOKEN` is valid
2. Check stream name configuration
3. Verify device ID mapping
4. Review DLQ for failed deliveries: `GET /api/v1/robotics/dlq`

**Webhook signature verification failing:**
1. Ensure `FORMANT_WEBHOOK_SECRET` matches Formant configuration
2. Verify webhook URL is configured correctly in Formant

**Incident acknowledgment failing:**
1. Verify API token has incident management permissions
2. Check incident ID is valid
3. Review Formant API logs

### Smoke Test

Run the Formant smoke test to verify connectivity:

```bash
# Requires valid credentials
PYTHONPATH=src python -c "
from tensorguard.integrations.connectors.robotics.formant_connector import FormantConnector
from tensorguard.integrations.connectors.robotics.config import get_formant_template

config = get_formant_template()
connector = FormantConnector(config)
result = connector.smoke_test()
print(f'Smoke test result: {result}')
"
```

## API Reference

### FormantConnector

```python
class FormantConnector(RoboticsOpsConnector):
    """Formant robotics platform connector."""

    async def send_event(self, event: OutboundOpsEvent) -> bool:
        """Send event to Formant data stream."""

    async def ingest_signal(
        self,
        raw_payload: dict,
        headers: dict | None = None
    ) -> InboundOpsSignal | None:
        """Process incoming Formant webhook."""

    async def acknowledge_incident(self, incident_id: str) -> bool:
        """Acknowledge incident in Formant (callback)."""

    def smoke_test(self) -> dict:
        """Test connectivity to Formant API."""
```

## Related Documentation

- [OPS Signal Model](./OPS_SIGNAL_MODEL.md)
- [InOrbit Integration](./INORBIT.md)
- [Foxglove Integration](./FOXGLOVE.md)
