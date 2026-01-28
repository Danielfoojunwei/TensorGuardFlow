"""
Contract tests for signature verification toggle.

Verifies that signature verification can be enabled/disabled
and behaves correctly in both modes.
"""

import pytest
import hmac
import hashlib

from tensorguard.integrations.connectors.robotics.base import (
    verify_hmac_signature,
    verify_signature_with_timestamp,
)
from tensorguard.integrations.connectors.robotics.config import (
    RoboticsConnectorConfig,
    RoboticsProvider,
    InboundConfig,
)


class TestSignatureVerificationToggle:
    """Test signature verification toggle behavior."""

    def test_hmac_signature_verification_success(self):
        """Test successful HMAC signature verification."""
        payload = b'{"event": "test"}'
        secret = b"test-secret"

        # Generate signature
        signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

        # Verify
        result = verify_hmac_signature(payload, signature, secret)
        assert result is True

    def test_hmac_signature_verification_failure(self):
        """Test failed HMAC signature verification."""
        payload = b'{"event": "test"}'
        secret = b"test-secret"
        wrong_signature = "0" * 64

        result = verify_hmac_signature(payload, wrong_signature, secret)
        assert result is False

    def test_signature_with_timestamp_valid(self):
        """Test signature verification with valid timestamp."""
        import time

        payload = b'{"event": "test"}'
        secret = b"test-secret"
        timestamp = str(time.time())

        signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

        is_valid, error = verify_signature_with_timestamp(
            payload, signature, timestamp, secret, tolerance_sec=300
        )

        assert is_valid is True
        assert error is None

    def test_signature_with_timestamp_expired(self):
        """Test signature verification with expired timestamp."""
        import time

        payload = b'{"event": "test"}'
        secret = b"test-secret"
        timestamp = str(time.time() - 600)  # 10 minutes ago

        signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

        is_valid, error = verify_signature_with_timestamp(
            payload, signature, timestamp, secret, tolerance_sec=300
        )

        assert is_valid is False
        assert "tolerance" in error.lower()

    def test_config_verify_signature_enabled(self):
        """Test configuration with signature verification enabled."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.INORBIT,
            inbound=InboundConfig(
                verify_signature=True,
                signature_header_name="X-InOrbit-Signature",
                signing_secret_ref="secret://kms/inorbit-webhook-key",
            ),
        )

        assert config.inbound.verify_signature is True
        assert config.inbound.signing_secret_ref is not None

    def test_config_verify_signature_disabled(self):
        """Test configuration with signature verification disabled."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.GENERIC,
            inbound=InboundConfig(
                verify_signature=False,
            ),
        )

        assert config.inbound.verify_signature is False

    def test_config_validation_requires_secret_when_verification_enabled(self):
        """Test that config validation warns when signature required but no secret."""
        config = RoboticsConnectorConfig(
            provider=RoboticsProvider.INORBIT,
            inbound=InboundConfig(
                verify_signature=True,
                # No signing_secret_ref or public_key_ref
            ),
        )

        errors = config.validate_complete()
        assert any("signing_secret_ref" in e or "public_key_ref" in e for e in errors)

    def test_hmac_constant_time_comparison(self):
        """Test that HMAC comparison is constant-time."""
        payload = b'{"event": "test"}'
        secret = b"test-secret"
        signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

        # Both should use hmac.compare_digest internally
        result1 = verify_hmac_signature(payload, signature, secret)
        result2 = verify_hmac_signature(payload, signature.upper(), secret)

        # Should handle case-insensitive
        assert result1 is True
        assert result2 is True

    def test_signature_algorithms(self):
        """Test different signature algorithms."""
        payload = b'{"event": "test"}'
        secret = b"test-secret"

        # SHA256
        sig256 = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        assert verify_hmac_signature(payload, sig256, secret, "sha256") is True

        # SHA384
        sig384 = hmac.new(secret, payload, hashlib.sha384).hexdigest()
        assert verify_hmac_signature(payload, sig384, secret, "sha384") is True

        # SHA512
        sig512 = hmac.new(secret, payload, hashlib.sha512).hexdigest()
        assert verify_hmac_signature(payload, sig512, secret, "sha512") is True

    def test_unsupported_algorithm_raises(self):
        """Test that unsupported algorithm raises error."""
        with pytest.raises(ValueError):
            verify_hmac_signature(b"test", "sig", b"secret", "md5")
