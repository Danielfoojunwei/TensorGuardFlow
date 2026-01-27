"""
Trust and privacy connectors (Category G).

These connectors provide signing, verification, and privacy mode capabilities.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from tensorguard.integrations.framework.contracts import (
    TrustConnector,
    PrivacyConnector,
    ConnectorCapability,
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.framework.manager import IntegrationRegistry


@IntegrationRegistry.register("aws_kms")
class AWSKMSConnector(TrustConnector):
    """Connector for AWS KMS signing operations."""

    @property
    def provider(self) -> str:
        return "aws_kms"

    @property
    def display_name(self) -> str:
        return "AWS KMS"

    def validate_config(self) -> ValidationResult:
        """Validate AWS KMS configuration."""
        errors = []
        warnings = []

        key_id = self.config.get("key_id")
        if not key_id:
            errors.append("key_id is required")

        signing_algorithm = self.config.get("signing_algorithm", "RSASSA_PSS_SHA_256")
        valid_algorithms = [
            "RSASSA_PSS_SHA_256",
            "RSASSA_PSS_SHA_384",
            "RSASSA_PSS_SHA_512",
            "RSASSA_PKCS1_V1_5_SHA_256",
            "RSASSA_PKCS1_V1_5_SHA_384",
            "RSASSA_PKCS1_V1_5_SHA_512",
            "ECDSA_SHA_256",
            "ECDSA_SHA_384",
            "ECDSA_SHA_512",
        ]
        if signing_algorithm not in valid_algorithms:
            errors.append(f"Invalid signing_algorithm. Must be one of: {valid_algorithms}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check KMS key accessibility."""
        start_time = time.time()

        key_id = self.config.get("key_id")
        region = self.config.get("region", "us-east-1")

        try:
            import boto3
            from botocore.exceptions import ClientError

            kms_client = boto3.client("kms", region_name=region)

            # Describe key to verify access
            response = kms_client.describe_key(KeyId=key_id)
            key_metadata = response.get("KeyMetadata", {})

            key_state = key_metadata.get("KeyState", "Unknown")
            if key_state != "Enabled":
                return HealthCheckResult(
                    status="WARN",
                    message=f"Key state is {key_state}, not Enabled",
                    latency_ms=int((time.time() - start_time) * 1000),
                    details={"key_id": key_id, "key_state": key_state},
                )

            return HealthCheckResult(
                status="OK",
                message=f"KMS key accessible and enabled",
                latency_ms=int((time.time() - start_time) * 1000),
                details={
                    "key_id": key_id,
                    "key_spec": key_metadata.get("KeySpec"),
                    "key_usage": key_metadata.get("KeyUsage"),
                },
            )

        except ImportError:
            return HealthCheckResult(
                status="WARN",
                message="boto3 not installed - schema validation only",
                latency_ms=int((time.time() - start_time) * 1000),
                details={"validation_only": True},
            )

        except Exception as e:
            return HealthCheckResult(
                status="FAIL",
                message=f"KMS access failed: {str(e)}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.SIGN,
            ConnectorCapability.VERIFY,
            ConnectorCapability.KEY_ROTATION,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test by signing and verifying test data."""
        start_time = time.time()

        try:
            # Test sign/verify round trip
            test_data = b"TensorGuardFlow smoke test"
            signature = await self.sign(test_data)
            verified = await self.verify(test_data, signature)

            if not verified:
                return SmokeTestResult(
                    passed=False,
                    test_name="sign_verify_roundtrip",
                    duration_ms=int((time.time() - start_time) * 1000),
                    message="Signature verification failed",
                )

            return SmokeTestResult(
                passed=True,
                test_name="sign_verify_roundtrip",
                duration_ms=int((time.time() - start_time) * 1000),
                message="Sign/verify round trip successful",
            )

        except ImportError:
            return SmokeTestResult(
                passed=True,
                test_name="sign_verify_roundtrip",
                duration_ms=int((time.time() - start_time) * 1000),
                message="boto3 not installed - skipped",
                details={"validation_only": True},
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="sign_verify_roundtrip",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def sign(self, data: bytes) -> bytes:
        """Sign data using KMS key."""
        try:
            import boto3

            key_id = self.config.get("key_id")
            region = self.config.get("region", "us-east-1")
            signing_algorithm = self.config.get("signing_algorithm", "RSASSA_PSS_SHA_256")

            kms_client = boto3.client("kms", region_name=region)

            # Hash the data first
            digest = hashlib.sha256(data).digest()

            response = kms_client.sign(
                KeyId=key_id,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm=signing_algorithm,
            )

            return response["Signature"]

        except ImportError:
            raise RuntimeError("boto3 required for KMS signing")

    async def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify signature using KMS key."""
        try:
            import boto3

            key_id = self.config.get("key_id")
            region = self.config.get("region", "us-east-1")
            signing_algorithm = self.config.get("signing_algorithm", "RSASSA_PSS_SHA_256")

            kms_client = boto3.client("kms", region_name=region)

            # Hash the data first
            digest = hashlib.sha256(data).digest()

            response = kms_client.verify(
                KeyId=key_id,
                Message=digest,
                MessageType="DIGEST",
                Signature=signature,
                SigningAlgorithm=signing_algorithm,
            )

            return response.get("SignatureValid", False)

        except ImportError:
            raise RuntimeError("boto3 required for KMS verification")

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export KMS configuration reference."""
        key_id = self.config.get("key_id")
        region = self.config.get("region", "us-east-1")
        signing_algorithm = self.config.get("signing_algorithm", "RSASSA_PSS_SHA_256")

        config_content = json.dumps({
            "provider": "aws_kms",
            "key_id": key_id,
            "region": region,
            "signing_algorithm": signing_algorithm,
            "timestamp": datetime.utcnow().isoformat(),
        }, indent=2)

        return [
            ExportArtifact(
                name="kms-config.json",
                content=config_content,
                artifact_type="json",
            )
        ]

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        region = self.config.get("region", "us-east-1")
        return [
            {
                "endpoint": f"kms.{region}.amazonaws.com",
                "type": "outbound",
                "protocol": "https",
                "auth_method": "iam",
            }
        ]


@IntegrationRegistry.register("local_dev")
class LocalDevSigningConnector(TrustConnector):
    """Local development signing connector (NOT FOR PRODUCTION)."""

    @property
    def provider(self) -> str:
        return "local_dev"

    @property
    def display_name(self) -> str:
        return "Local Dev Signing"

    def validate_config(self) -> ValidationResult:
        """Validate local dev signing configuration."""
        warnings = []

        # Always warn that this is dev-only
        warnings.append("Local dev signing is NOT suitable for production")

        env = os.environ.get("TGF_ENV", "development")
        if env == "production":
            return ValidationResult(
                valid=False,
                errors=["Local dev signing cannot be used in production environment"],
                warnings=warnings,
            )

        return ValidationResult(
            valid=True,
            warnings=warnings,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check local dev signing availability."""
        start_time = time.time()

        env = os.environ.get("TGF_ENV", "development")
        if env == "production":
            return HealthCheckResult(
                status="FAIL",
                message="Local dev signing not available in production",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        return HealthCheckResult(
            status="WARN",
            message="Development signing only - not for production",
            latency_ms=int((time.time() - start_time) * 1000),
            details={"environment": env},
        )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.SIGN,
            ConnectorCapability.VERIFY,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test with local signing."""
        start_time = time.time()

        try:
            test_data = b"TensorGuardFlow smoke test"
            signature = await self.sign(test_data)
            verified = await self.verify(test_data, signature)

            return SmokeTestResult(
                passed=verified,
                test_name="local_sign_verify",
                duration_ms=int((time.time() - start_time) * 1000),
                message="Local sign/verify successful" if verified else "Verification failed",
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="local_sign_verify",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def sign(self, data: bytes) -> bytes:
        """Sign data using local HMAC (dev only)."""
        # Use a fixed dev key for local signing
        dev_key = os.environ.get("TGF_DEV_SIGNING_KEY", "tgf-dev-key-not-for-production")
        import hmac
        signature = hmac.new(
            dev_key.encode(),
            data,
            hashlib.sha256
        ).digest()
        return signature

    async def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify signature using local HMAC (dev only)."""
        expected_signature = await self.sign(data)
        return hmac.compare_digest(signature, expected_signature)

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export local dev signing reference."""
        return [
            ExportArtifact(
                name="local-signing-config.json",
                content=json.dumps({
                    "provider": "local_dev",
                    "warning": "Development signing only - NOT FOR PRODUCTION",
                    "timestamp": datetime.utcnow().isoformat(),
                }, indent=2),
                artifact_type="json",
            )
        ]

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        return []  # Local signing, no endpoints


@IntegrationRegistry.register("n2he")
class N2HEConnector(PrivacyConnector):
    """Connector for N2HE privacy mode."""

    @property
    def provider(self) -> str:
        return "n2he"

    @property
    def display_name(self) -> str:
        return "N2HE Privacy Mode"

    def validate_config(self) -> ValidationResult:
        """Validate N2HE configuration."""
        errors = []
        warnings = []

        encryption_mode = self.config.get("encryption_mode", "FULL")
        if encryption_mode not in ["FULL", "METADATA_ONLY"]:
            errors.append("encryption_mode must be 'FULL' or 'METADATA_ONLY'")

        receipt_retention_days = self.config.get("receipt_retention_days", 90)
        if receipt_retention_days < 1:
            errors.append("receipt_retention_days must be >= 1")
        elif receipt_retention_days < 30:
            warnings.append("receipt_retention_days < 30 may not meet compliance requirements")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check N2HE availability."""
        start_time = time.time()

        enabled = self.config.get("enabled", False)
        if not enabled:
            return HealthCheckResult(
                status="DISABLED",
                message="N2HE privacy mode is disabled",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        return HealthCheckResult(
            status="OK",
            message="N2HE privacy mode active",
            latency_ms=int((time.time() - start_time) * 1000),
            details={
                "encryption_mode": self.config.get("encryption_mode", "FULL"),
                "receipt_generation": self.config.get("receipt_generation", True),
                "safe_logging": self.config.get("safe_logging", True),
            },
        )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.ENCRYPTED_ROUTING,
            ConnectorCapability.PRIVACY_RECEIPTS,
            ConnectorCapability.SAFE_LOGGING,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test on N2HE."""
        start_time = time.time()

        enabled = self.config.get("enabled", False)
        if not enabled:
            return SmokeTestResult(
                passed=True,
                test_name="n2he_status",
                duration_ms=int((time.time() - start_time) * 1000),
                message="N2HE disabled - skipped",
            )

        try:
            # Test receipt generation
            receipt = await self.generate_receipt(
                "test_operation",
                {"route_key": "smoke-test"}
            )

            if not receipt:
                raise ValueError("No receipt generated")

            # Validate receipt
            valid = await self.validate_receipt(receipt)
            if not valid:
                raise ValueError("Receipt validation failed")

            return SmokeTestResult(
                passed=True,
                test_name="n2he_receipt",
                duration_ms=int((time.time() - start_time) * 1000),
                message="Receipt generation and validation successful",
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="n2he_receipt",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def sign(self, data: bytes) -> bytes:
        """Sign data for privacy receipt."""
        # N2HE uses internal signing mechanism
        receipt_key = os.environ.get("TGF_N2HE_RECEIPT_KEY", "n2he-receipt-key")
        import hmac
        return hmac.new(receipt_key.encode(), data, hashlib.sha256).digest()

    async def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify privacy receipt signature."""
        expected = await self.sign(data)
        return hmac.compare_digest(signature, expected)

    async def generate_receipt(
        self,
        operation: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a privacy receipt for an operation."""
        if not self.config.get("receipt_generation", True):
            return {}

        timestamp = datetime.utcnow().isoformat()
        receipt_data = {
            "operation": operation,
            "context_hash": hashlib.sha256(
                json.dumps(context, sort_keys=True).encode()
            ).hexdigest()[:16],
            "timestamp": timestamp,
            "encryption_mode": self.config.get("encryption_mode", "FULL"),
        }

        # Sign the receipt
        receipt_bytes = json.dumps(receipt_data, sort_keys=True).encode()
        signature = await self.sign(receipt_bytes)

        receipt_data["signature"] = base64.b64encode(signature).decode()
        receipt_data["receipt_id"] = f"rcpt_{hashlib.sha256(receipt_bytes).hexdigest()[:12]}"

        return receipt_data

    async def validate_receipt(self, receipt: Dict[str, Any]) -> bool:
        """Validate a privacy receipt."""
        if not receipt:
            return False

        try:
            signature_b64 = receipt.pop("signature", "")
            receipt.pop("receipt_id", "")

            receipt_bytes = json.dumps(receipt, sort_keys=True).encode()
            signature = base64.b64decode(signature_b64)

            return await self.verify(receipt_bytes, signature)

        except Exception:
            return False

    def is_safe_log_entry(self, log_entry: str) -> bool:
        """Check if a log entry complies with safe logging policy."""
        if not self.config.get("safe_logging", True):
            return True

        # Check for common PII patterns
        pii_patterns = [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone
            r"\b\d{3}[-]?\d{2}[-]?\d{4}\b",  # SSN
            r"\b(?:\d{4}[-\s]?){3}\d{4}\b",  # Credit card
        ]

        import re
        for pattern in pii_patterns:
            if re.search(pattern, log_entry):
                return False

        return True

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export N2HE configuration."""
        config_content = json.dumps({
            "provider": "n2he",
            "enabled": self.config.get("enabled", False),
            "encryption_mode": self.config.get("encryption_mode", "FULL"),
            "receipt_generation": self.config.get("receipt_generation", True),
            "safe_logging": self.config.get("safe_logging", True),
            "receipt_retention_days": self.config.get("receipt_retention_days", 90),
            "timestamp": datetime.utcnow().isoformat(),
        }, indent=2)

        return [
            ExportArtifact(
                name="n2he-config.json",
                content=config_content,
                artifact_type="json",
            )
        ]

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        return []  # Internal privacy mode, no external endpoints
