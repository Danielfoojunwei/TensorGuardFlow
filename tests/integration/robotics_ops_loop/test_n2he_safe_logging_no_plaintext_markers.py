"""
Integration test: N2HE safe logging.

Verifies that N2HE privacy mode prevents plaintext identifiers in logs.
"""

import pytest
import json

from tensorguard.integrations.connectors.robotics.schemas import (
    OutboundOpsEvent,
    InboundOpsSignal,
    SignalPayload,
    AuthInfo,
    EventPayload,
    SignalSource,
    InboundSignalType,
    Severity,
    EventCategory,
    OutboundEventType,
)
from tensorguard.integrations.connectors.robotics.inorbit_connector import InOrbitConnector
from tensorguard.integrations.connectors.robotics.config import (
    RoboticsConnectorConfig,
    RoboticsProvider,
    N2HEIntegrationConfig,
)


class TestN2HESafeLogging:
    """Test N2HE safe logging behavior."""

    @pytest.fixture
    def n2he_enabled_config(self):
        """Configuration with N2HE enabled."""
        return {
            "provider": "inorbit",
            "n2he": {
                "enabled": True,
                "redact_identifiers_in_logs": True,
                "encrypt_stored_payloads": True,
            },
            "outbound": {
                "mode": "webhook",
                "target_url": "https://example.com/webhook",
            },
        }

    @pytest.fixture
    def n2he_disabled_config(self):
        """Configuration with N2HE disabled."""
        return {
            "provider": "inorbit",
            "n2he": {
                "enabled": False,
            },
            "outbound": {
                "mode": "webhook",
                "target_url": "https://example.com/webhook",
            },
        }

    @pytest.fixture
    def sample_event(self):
        """Sample outbound event with identifiable info."""
        return OutboundOpsEvent(
            tenant_id="tenant-robotics-corp",
            route_key="nav-policy-prod",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Adapter promoted",
            payload=EventPayload(
                adapter_id="adpt_secret123",
                run_id="run-20260128-sensitive",
            ),
        )

    @pytest.fixture
    def sample_signal(self):
        """Sample inbound signal with identifiable info."""
        return InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="tenant-robotics-corp",
            route_key="nav-policy-prod",
            severity=Severity.WARN,
            type=InboundSignalType.INCIDENT,
            payload=SignalPayload(
                raw={
                    "robot_id": "robot-alpha-001",
                    "secret_token": "abc123",
                },
            ),
            auth=AuthInfo(signature_present=True, verified=True),
            dedupe_key="test-dedupe-key",
        )

    def test_n2he_enabled_redacts_event_identifiers(
        self,
        n2he_enabled_config,
        sample_event,
    ):
        """Test that N2HE mode redacts event identifiers in logs."""
        connector = InOrbitConnector(n2he_enabled_config)

        safe_log = connector.safe_log_event(sample_event)

        # Route key and tenant_id should be redacted
        assert safe_log["route_key"] == "[N2HE_REDACTED]"
        assert safe_log["tenant_id"] == "[N2HE_REDACTED]"

        # Event ID and type should still be visible for debugging
        assert safe_log["event_id"] == sample_event.event_id
        assert safe_log["type"] == sample_event.type.value

    def test_n2he_disabled_shows_identifiers(
        self,
        n2he_disabled_config,
        sample_event,
    ):
        """Test that identifiers are visible when N2HE disabled."""
        connector = InOrbitConnector(n2he_disabled_config)

        safe_log = connector.safe_log_event(sample_event)

        # Identifiers should be visible
        assert safe_log["route_key"] == "nav-policy-prod"
        assert safe_log["tenant_id"] == "tenant-robotics-corp"

    def test_n2he_enabled_redacts_signal_identifiers(
        self,
        n2he_enabled_config,
        sample_signal,
    ):
        """Test that N2HE mode redacts signal identifiers in logs."""
        connector = InOrbitConnector(n2he_enabled_config)

        safe_log = connector.safe_log_signal(sample_signal)

        # Route key should be redacted
        assert safe_log["route_key"] == "[N2HE_REDACTED]"

        # Signal ID should still be visible
        assert safe_log["signal_id"] == sample_signal.signal_id

    def test_safe_log_never_includes_raw_payload(
        self,
        n2he_disabled_config,
        sample_signal,
    ):
        """Test that safe_log never includes raw payload even without N2HE."""
        connector = InOrbitConnector(n2he_disabled_config)

        safe_log = connector.safe_log_signal(sample_signal)
        safe_log_str = json.dumps(safe_log)

        # Raw payload secrets should never appear
        assert "secret_token" not in safe_log_str
        assert "abc123" not in safe_log_str

    def test_safe_log_truncates_dedupe_key(
        self,
        n2he_disabled_config,
        sample_signal,
    ):
        """Test that dedupe_key is truncated in logs."""
        connector = InOrbitConnector(n2he_disabled_config)

        safe_log = connector.safe_log_signal(sample_signal)

        # Dedupe key should be truncated
        assert safe_log["dedupe_key"].endswith("...")
        assert len(safe_log["dedupe_key"]) < len(sample_signal.dedupe_key)

    def test_config_snapshot_redacts_secrets(
        self,
        n2he_enabled_config,
    ):
        """Test that config snapshot redacts secrets."""
        config = dict(n2he_enabled_config)
        config["outbound"]["secret_ref"] = "super-secret-key"
        config["inbound"] = {"signing_secret_ref": "webhook-secret"}

        connector = InOrbitConnector(config)

        safe_config = connector._get_safe_config_snapshot()

        # Secrets should be redacted
        assert safe_config["outbound"].get("secret_ref") == "[REDACTED]"
        assert safe_config["inbound"].get("signing_secret_ref") == "[REDACTED]"

        # Non-secret fields should be visible
        assert safe_config["provider"] == "inorbit"

    def test_no_plaintext_markers_in_n2he_mode(
        self,
        n2he_enabled_config,
        sample_event,
        sample_signal,
    ):
        """Comprehensive test that no plaintext markers leak."""
        connector = InOrbitConnector(n2he_enabled_config)

        # Get all log outputs
        event_log = json.dumps(connector.safe_log_event(sample_event))
        signal_log = json.dumps(connector.safe_log_signal(sample_signal))
        config_log = json.dumps(connector._get_safe_config_snapshot())

        all_logs = event_log + signal_log + config_log

        # Check for common identifiable patterns
        sensitive_patterns = [
            "tenant-robotics-corp",
            "nav-policy-prod",
            "robot-alpha-001",
            "secret",
            "password",
            "token",
            "adpt_secret123",
        ]

        for pattern in sensitive_patterns:
            assert pattern not in all_logs, f"Found sensitive pattern: {pattern}"

    def test_n2he_config_validation(self):
        """Test N2HE configuration validation."""
        config = N2HEIntegrationConfig(
            enabled=True,
            redact_identifiers_in_logs=True,
            encrypt_stored_payloads=True,
            privacy_overhead_tracking=True,
        )

        assert config.enabled is True
        assert config.redact_identifiers_in_logs is True
        assert config.encrypt_stored_payloads is True
