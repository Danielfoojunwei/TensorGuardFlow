# Foxglove Integration Guide

TensorGuardFlow integration with [Foxglove](https://foxglove.dev/) for robotics visualization and data recording.

## Overview

Foxglove is a robotics visualization and debugging platform that provides data playback, live visualization, and MCAP recording. TensorGuardFlow integrates with Foxglove to:

- **Outbound**: Push PEFT deployment events, model metrics, and MCAP bundle pointers for debugging
- **Inbound**: Receive annotation signals and user-tagged events for investigation

## Architecture

```
┌─────────────────────┐          ┌─────────────────────┐
│   TensorGuardFlow   │          │      Foxglove       │
│                     │          │                     │
│  ┌───────────────┐  │  Events  │  ┌───────────────┐  │
│  │ Foxglove      │──┼─────────>│  │ Data Lake /   │  │
│  │ Connector     │  │          │  │ Recordings    │  │
│  │               │<─┼──────────│  │               │  │
│  └───────────────┘  │ Webhooks │  │ Annotations   │  │
│         │          │          │  │ & Events      │  │
│         v          │          └─────────────────────┘
│  ┌───────────────┐  │
│  │ MCAP Bundle   │  │
│  │ Pointers      │  │
│  └───────────────┘  │
└─────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Required
FOXGLOVE_API_KEY=your_api_key_here
FOXGLOVE_ORGANIZATION_ID=your_org_id

# Optional
FOXGLOVE_API_URL=https://api.foxglove.dev  # Default
FOXGLOVE_WEBHOOK_SECRET=your_webhook_secret  # For signature verification
FOXGLOVE_DATA_LAKE_URL=https://data.foxglove.dev  # For MCAP uploads
```

### Connector Configuration

```python
from tensorguard.integrations.connectors.robotics.config import get_foxglove_template

# Get default configuration template
config = get_foxglove_template()

# Customize as needed
config.outbound.enabled = True
config.inbound.enabled = True
```

### Full Configuration Example

```yaml
# config/robotics/foxglove.yaml
provider: foxglove
enabled: true

outbound:
  enabled: true
  endpoint: https://api.foxglove.dev/v1/events
  event_types:
    - peft_deployment_started
    - peft_deployment_completed
    - peft_deployment_failed
    - drift_detected
    - model_snapshot_created
  batch_size: 5
  flush_interval_seconds: 60
  retry_policy:
    max_retries: 3
    backoff_base_seconds: 2
    backoff_max_seconds: 60

inbound:
  enabled: true
  webhook_path: /api/v1/robotics/webhook/foxglove
  require_signature: false  # Foxglove webhooks are typically internal
  signature_header: X-Foxglove-Signature
  timestamp_tolerance_seconds: 300
  allowed_signal_types:
    - annotation_created
    - recording_tagged
    - event_flagged

replay_protection:
  enabled: true
  cache_size: 5000
  ttl_seconds: 3600

n2he_privacy:
  enabled: true
  redact_robot_ids: true
  redact_location_data: true

# Foxglove-specific settings
foxglove_specific:
  enable_mcap_export: true
  mcap_upload_bucket: tensorguardflow-mcap-exports
  recording_retention_days: 30
  link_recordings_to_events: true
```

## Outbound Events

### Event Types

| Event Type | Description | Foxglove Mapping |
|------------|-------------|------------------|
| `peft_deployment_started` | PEFT update deployment initiated | Event marker |
| `peft_deployment_completed` | PEFT update successfully deployed | Event marker |
| `peft_deployment_failed` | PEFT update deployment failed | Event marker + annotation |
| `drift_detected` | Model drift detected | Event marker + annotation |
| `model_snapshot_created` | Model checkpoint saved | Event marker with MCAP pointer |

### Event Payload Format

TensorGuardFlow events are transformed to Foxglove's event format:

```json
{
  "deviceId": "fleet-robot-001",
  "timestamp": "2026-01-28T12:00:00Z",
  "event": {
    "type": "tensorguardflow.peft_deployment_completed",
    "metadata": {
      "model_id": "model-abc123",
      "adapter_id": "adapter-xyz789",
      "version": "v2.1.0",
      "validation_score": 0.95
    }
  }
}
```

### MCAP Bundle Pointers

When model snapshots or debugging data is available, TensorGuardFlow can generate MCAP bundle pointers that link Foxglove recordings to specific events:

```json
{
  "mcap_bundle": {
    "pointer_id": "mcap-ptr-uuid-123",
    "storage_uri": "s3://tensorguardflow-mcap/bundles/2026-01-28/bundle-abc.mcap",
    "recording_id": "rec-12345",
    "time_range": {
      "start": "2026-01-28T11:55:00Z",
      "end": "2026-01-28T12:05:00Z"
    },
    "topics": [
      "/model/inference",
      "/model/metrics",
      "/tensorguardflow/events"
    ],
    "size_bytes": 52428800,
    "checksum": "sha256:abc123..."
  }
}
```

## Inbound Signals

### Supported Signal Types

| Foxglove Event | TensorGuardFlow Signal | Default Action |
|----------------|------------------------|----------------|
| `annotation.created` (error) | `error_annotation` | `investigate` |
| `annotation.created` (critical) | `critical_annotation` | `quarantine` |
| `recording.tagged` (investigate) | `investigation_request` | `investigate` |
| `event.flagged` | `flagged_event` | `investigate` |

### Webhook Payload Example

Foxglove sends webhooks for annotations and events:

```json
{
  "type": "annotation.created",
  "timestamp": "2026-01-28T12:00:00Z",
  "organization_id": "org-12345",
  "data": {
    "annotation_id": "ann-67890",
    "recording_id": "rec-12345",
    "device_id": "fleet-robot-001",
    "severity": "critical",
    "message": "Model produced unexpected output at timestamp",
    "time_range": {
      "start": "2026-01-28T11:59:30Z",
      "end": "2026-01-28T12:00:30Z"
    },
    "created_by": "operator@company.com"
  }
}
```

### Investigation Workflow

Foxglove signals typically trigger investigation workflows rather than immediate rollbacks:

1. Operator creates annotation in Foxglove
2. Webhook triggers TensorGuardFlow signal
3. TensorGuardFlow creates investigation ticket
4. MCAP bundle pointer is attached for debugging context

## Security Considerations

### Credential Management

- Store `FOXGLOVE_API_KEY` in your secrets manager
- Never log or expose API keys
- Use BYOKMS if available for key rotation

### MCAP Storage Security

- MCAP bundles may contain sensitive sensor data
- Use encrypted storage (S3 SSE, GCS CMEK)
- Apply appropriate IAM policies for access control

### N2HE Privacy Mode

When N2HE privacy mode is enabled:
- Device IDs are hashed before logging
- Location data is redacted from MCAP pointers
- Only privacy-safe metadata is logged

## Troubleshooting

### Common Issues

**Events not appearing in Foxglove:**
1. Verify `FOXGLOVE_API_KEY` is valid
2. Check organization ID configuration
3. Review DLQ for failed deliveries: `GET /api/v1/robotics/dlq`

**MCAP bundle upload failing:**
1. Verify storage bucket permissions
2. Check network connectivity to data lake
3. Verify file size limits

**Annotations not triggering signals:**
1. Verify webhook URL is configured in Foxglove
2. Check allowed_signal_types configuration
3. Review inbound configuration

### Smoke Test

Run the Foxglove smoke test to verify connectivity:

```bash
# Requires valid credentials
PYTHONPATH=src python -c "
from tensorguard.integrations.connectors.robotics.foxglove_connector import FoxgloveConnector
from tensorguard.integrations.connectors.robotics.config import get_foxglove_template

config = get_foxglove_template()
connector = FoxgloveConnector(config)
result = connector.smoke_test()
print(f'Smoke test result: {result}')
"
```

## API Reference

### FoxgloveConnector

```python
class FoxgloveConnector(RoboticsOpsConnector):
    """Foxglove robotics visualization platform connector."""

    async def send_event(self, event: OutboundOpsEvent) -> bool:
        """Send event to Foxglove."""

    async def ingest_signal(
        self,
        raw_payload: dict,
        headers: dict | None = None
    ) -> InboundOpsSignal | None:
        """Process incoming Foxglove webhook."""

    def generate_mcap_bundle_pointer(
        self,
        recording_id: str,
        time_range: tuple[str, str],
        topics: list[str] | None = None
    ) -> dict:
        """Generate MCAP bundle pointer for Foxglove recording."""

    def smoke_test(self) -> dict:
        """Test connectivity to Foxglove API."""
```

### MCAP Bundle Pointer Generation

```python
# Generate pointer for a specific time range
pointer = connector.generate_mcap_bundle_pointer(
    recording_id="rec-12345",
    time_range=("2026-01-28T11:55:00Z", "2026-01-28T12:05:00Z"),
    topics=["/model/inference", "/model/metrics"]
)

# Include in outbound event
event.payload.mcap_bundle_pointer = pointer
```

## Related Documentation

- [OPS Signal Model](./OPS_SIGNAL_MODEL.md)
- [InOrbit Integration](./INORBIT.md)
- [Formant Integration](./FORMANT.md)
