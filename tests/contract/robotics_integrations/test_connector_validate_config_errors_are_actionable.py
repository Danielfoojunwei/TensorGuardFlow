"""
Contract tests for connector configuration validation.

Verifies that configuration validation returns actionable error messages.
"""

import pytest

from tensorguard.integrations.connectors.robotics.config import (
    RoboticsConnectorConfig,
    RoboticsProvider,
    OutboundConfig,
    InboundConfig,
    OutboundMode,
    AuthType,
)
from tensorguard.integrations.connectors.robotics.inorbit_connector import InOrbitConnector
from tensorguard.integrations.connectors.robotics.formant_connector import FormantConnector
from tensorguard.integrations.connectors.robotics.foxglove_connector import FoxgloveConnector


class TestConnectorConfigValidation:
    """Test connector configuration validation returns actionable errors."""

    def test_missing_webhook_url_error_is_actionable(self):
        """Test that missing webhook URL produces actionable error."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.INORBIT,
            outbound=OutboundConfig(
                mode=OutboundMode.WEBHOOK,
                # Missing target_url
            ),
        )

        errors = config.validate_complete()
        assert len(errors) > 0
        assert any("target_url" in e for e in errors)

    def test_missing_api_base_url_error_is_actionable(self):
        """Test that missing API base URL produces actionable error."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.FORMANT,
            outbound=OutboundConfig(
                mode=OutboundMode.API,
                # Missing api_base_url
            ),
        )

        errors = config.validate_complete()
        assert len(errors) > 0
        assert any("api_base_url" in e for e in errors)

    def test_missing_auth_secret_error_is_actionable(self):
        """Test that missing auth secret produces actionable error."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.INORBIT,
            outbound=OutboundConfig(
                mode=OutboundMode.WEBHOOK,
                target_url="https://example.com/webhook",
                auth_type=AuthType.BEARER,
                # Missing secret_ref
            ),
        )

        errors = config.validate_complete()
        assert len(errors) > 0
        assert any("secret_ref" in e for e in errors)

    def test_inorbit_connector_validation_errors(self):
        """Test InOrbit connector validation produces actionable errors."""
        config = {
            "provider": "inorbit",
            "outbound": {
                "mode": "webhook",
                # Missing target_url
            },
            "inbound": {
                "verify_signature": True,
                # Missing signing_secret_ref
            },
        }

        connector = InOrbitConnector(config)
        result = connector.validate_config()

        assert result.valid is False
        assert len(result.errors) > 0
        # Errors should be specific and actionable
        for error in result.errors:
            assert len(error) > 10  # Not just a field name

    def test_formant_connector_validation_errors(self):
        """Test Formant connector validation produces actionable errors."""
        config = {
            "provider": "formant",
            "outbound": {
                "mode": "api",
                # Missing api_base_url
            },
        }

        connector = FormantConnector(config)
        result = connector.validate_config()

        assert result.valid is False
        assert len(result.errors) > 0

    def test_foxglove_connector_validation_errors(self):
        """Test Foxglove connector validation produces actionable errors."""
        config = {
            "provider": "foxglove",
            "outbound": {
                "mode": "webhook",
                # Missing target_url
            },
        }

        connector = FoxgloveConnector(config)
        result = connector.validate_config()

        assert result.valid is False
        assert len(result.errors) > 0

    def test_valid_config_passes_validation(self):
        """Test that valid configuration passes validation."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.INORBIT,
            outbound=OutboundConfig(
                mode=OutboundMode.WEBHOOK,
                target_url="https://api.inorbit.ai/webhook",
                auth_type=AuthType.BEARER,
                secret_ref="secret://kms/inorbit-api-key",
            ),
            inbound=InboundConfig(
                verify_signature=False,  # Disabled, so no secret needed
            ),
        )

        errors = config.validate_complete()
        assert len(errors) == 0

    def test_validation_includes_suggestions(self):
        """Test that validation includes helpful suggestions."""
        config = {
            "provider": "inorbit",
            "outbound": {
                "mode": "webhook",
                "target_url": "https://example.com/webhook",
                "auth_type": "none",
            },
            "inbound": {
                "verify_signature": True,
                "signature_header_name": "X-Custom-Sig",  # Not standard
                "signing_secret_ref": "secret://test",
            },
        }

        connector = InOrbitConnector(config)
        result = connector.validate_config()

        # Should suggest using X-InOrbit-Signature
        assert len(result.suggestions) > 0 or len(result.warnings) > 0

    def test_url_format_validation(self):
        """Test URL format validation."""
        with pytest.raises(ValueError):
            OutboundConfig(
                mode=OutboundMode.WEBHOOK,
                target_url="not-a-url",  # Invalid URL
            )

    def test_retry_policy_bounds(self):
        """Test retry policy parameter bounds."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.GENERIC,
            outbound=OutboundConfig(
                mode=OutboundMode.WEBHOOK,
                target_url="https://example.com",
            ),
        )

        # Should have reasonable defaults
        assert config.outbound.retry_policy.max_retries <= 20
        assert config.outbound.retry_policy.initial_delay_ms >= 100
        assert config.outbound.retry_policy.max_delay_ms <= 600000

    def test_config_fingerprint_excludes_secrets(self):
        """Test that config fingerprint excludes secret values."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.INORBIT,
            outbound=OutboundConfig(
                mode=OutboundMode.WEBHOOK,
                target_url="https://example.com",
                auth_type=AuthType.BEARER,
                secret_ref="secret://kms/my-secret",
            ),
        )

        fingerprint = config.compute_fingerprint()

        # Fingerprint should be deterministic
        assert fingerprint == config.compute_fingerprint()

        # Different secret refs should produce same fingerprint
        # (secrets excluded from fingerprint)
        config2 = RoboticsConnectorConfig(
            provider=RoboticsProvider.INORBIT,
            outbound=OutboundConfig(
                mode=OutboundMode.WEBHOOK,
                target_url="https://example.com",
                auth_type=AuthType.BEARER,
                secret_ref="secret://kms/different-secret",
            ),
        )

        assert config.compute_fingerprint() == config2.compute_fingerprint()
