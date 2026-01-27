"""
Integration connector contracts and base classes.

This module defines the contract that all integration connectors must implement,
ensuring consistent behavior across all external system integrations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib


class ConnectorCapability(str, Enum):
    """Capabilities that a connector can provide."""
    # Data capabilities
    READ_DATA = "read_data"
    HASH_VERIFICATION = "hash_verification"
    VERSIONING = "versioning"
    STREAMING = "streaming"

    # Training capabilities
    LOCAL_TRAINING = "local_training"
    REMOTE_TRAINING = "remote_training"
    JOB_EXPORT = "job_export"
    GPU_SCHEDULING = "gpu_scheduling"
    MIXED_PRECISION = "mixed_precision"

    # Registry/tracking capabilities
    ADAPTER_REGISTRY = "adapter_registry"
    CHANNEL_MANAGEMENT = "channel_management"
    EVIDENCE_CHAIN = "evidence_chain"
    GATE_EVALUATION = "gate_evaluation"
    TGSP_PACKAGING = "tgsp_packaging"
    METRICS_SINK = "metrics_sink"
    EXPERIMENT_TRACKING = "experiment_tracking"

    # Serving capabilities
    SERVING_PACK_EXPORT = "serving_pack_export"
    RESOLVE_INTEGRATION = "resolve_integration"
    LORA_LOADING = "lora_loading"
    DYNAMIC_ADAPTER = "dynamic_adapter"

    # Trust capabilities
    SIGN = "sign"
    VERIFY = "verify"
    KEY_ROTATION = "key_rotation"
    ENCLAVE_ATTESTATION = "enclave_attestation"
    ENCRYPTED_ROUTING = "encrypted_routing"
    PRIVACY_RECEIPTS = "privacy_receipts"
    SAFE_LOGGING = "safe_logging"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    status: str  # OK, WARN, FAIL, UNKNOWN
    message: str
    latency_ms: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        return self.status in ("OK", "WARN")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class ValidationResult:
    """Result of a configuration validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


@dataclass
class SmokeTestResult:
    """Result of a smoke test operation."""
    passed: bool
    test_name: str
    duration_ms: int
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "test_name": self.test_name,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class ExportArtifact:
    """An exported artifact from a connector."""
    name: str
    content: str  # or bytes for binary
    artifact_type: str  # yaml, json, pbtxt, etc.
    checksum: Optional[str] = None
    path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.checksum is None:
            content_bytes = (
                self.content.encode()
                if isinstance(self.content, str)
                else self.content
            )
            self.checksum = hashlib.sha256(content_bytes).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "artifact_type": self.artifact_type,
            "checksum": self.checksum,
            "path": self.path,
            "metadata": self.metadata,
        }


class IntegrationConnector(ABC):
    """
    Base class for all integration connectors.

    Each connector must implement these core operations:
    - validate_config: Check if configuration is valid
    - health_check: Verify connectivity and permissions
    - capabilities: List what this connector can do
    - smoke_test: Run a quick operational test
    - export_artifacts: Generate platform-specific artifacts
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize connector with configuration."""
        self.config = config
        self._validated = False
        self._last_health_check: Optional[HealthCheckResult] = None

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the provider identifier (e.g., 'aws_s3', 'kubernetes')."""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """Return the category (C, D, E, F, or G)."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return human-readable name for display."""
        pass

    @abstractmethod
    def validate_config(self) -> ValidationResult:
        """
        Validate the connector configuration.

        Returns:
            ValidationResult indicating if config is valid with any errors/warnings.
        """
        pass

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """
        Perform a health check on the integration.

        This should verify:
        - Connectivity to the external system
        - Authentication is valid
        - Required permissions exist

        Returns:
            HealthCheckResult with status and details.
        """
        pass

    @abstractmethod
    def capabilities(self) -> List[ConnectorCapability]:
        """
        Return list of capabilities this connector provides.

        Returns:
            List of ConnectorCapability enums.
        """
        pass

    @abstractmethod
    async def smoke_test(self) -> SmokeTestResult:
        """
        Run a quick operational test.

        This should test basic operations without side effects:
        - For data sources: list/head a file
        - For training: validate job spec generation
        - For signing: test sign/verify round-trip

        Returns:
            SmokeTestResult with pass/fail and details.
        """
        pass

    @abstractmethod
    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """
        Generate platform-specific artifacts.

        Args:
            context: Context containing route_key, run_id, adapter info, etc.

        Returns:
            List of ExportArtifact objects.
        """
        pass

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        """
        Return list of endpoints this connector uses.

        Override in subclasses to provide endpoint details.
        """
        return []

    def get_config_fingerprint(self) -> str:
        """Compute deterministic hash of configuration."""
        import json
        serialized = json.dumps(self.config, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"

    async def refresh_health(self) -> HealthCheckResult:
        """Run health check and cache result."""
        self._last_health_check = await self.health_check()
        return self._last_health_check

    def get_last_health_check(self) -> Optional[HealthCheckResult]:
        """Get cached health check result."""
        return self._last_health_check


class DataSourceConnector(IntegrationConnector):
    """Base class for data source connectors (Category C)."""

    @property
    def category(self) -> str:
        return "C"

    @abstractmethod
    async def list_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List objects in the data source."""
        pass

    @abstractmethod
    async def get_object_hash(self, key: str) -> str:
        """Get hash of a specific object."""
        pass

    @abstractmethod
    async def get_object_metadata(self, key: str) -> Dict[str, Any]:
        """Get metadata for a specific object."""
        pass


class TrainingConnector(IntegrationConnector):
    """Base class for training execution connectors (Category D)."""

    @property
    def category(self) -> str:
        return "D"

    @abstractmethod
    async def export_job_spec(
        self,
        context: Dict[str, Any],
    ) -> ExportArtifact:
        """Export training job specification."""
        pass

    async def submit_job(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a training job (optional, requires TG_ENABLE_REMOTE_SUBMIT=true).

        Default implementation raises NotImplementedError.
        """
        import os
        if not os.environ.get("TG_ENABLE_REMOTE_SUBMIT", "").lower() == "true":
            raise NotImplementedError(
                "Remote job submission is disabled. "
                "Set TG_ENABLE_REMOTE_SUBMIT=true to enable."
            )
        return await self._submit_job_impl(context)

    async def _submit_job_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Actual job submission implementation. Override in subclasses."""
        raise NotImplementedError("Job submission not implemented for this connector.")


class TrackingConnector(IntegrationConnector):
    """Base class for tracking/metrics sink connectors (Category E)."""

    @property
    def category(self) -> str:
        return "E"

    @abstractmethod
    async def log_metrics(
        self,
        run_id: str,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log metrics to tracking system."""
        pass

    @abstractmethod
    async def log_params(self, run_id: str, params: Dict[str, Any]) -> None:
        """Log parameters to tracking system."""
        pass

    @abstractmethod
    async def log_artifact(
        self,
        run_id: str,
        artifact_path: str,
        artifact_name: Optional[str] = None,
    ) -> None:
        """Log an artifact to tracking system."""
        pass


class ServingConnector(IntegrationConnector):
    """Base class for serving/inference connectors (Category F)."""

    @property
    def category(self) -> str:
        return "F"

    @abstractmethod
    async def export_serving_pack(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export serving configuration pack."""
        pass

    @abstractmethod
    def get_resolve_integration_code(self) -> str:
        """Return code snippet for /resolve integration."""
        pass


class TrustConnector(IntegrationConnector):
    """Base class for trust & privacy connectors (Category G)."""

    @property
    def category(self) -> str:
        return "G"

    @abstractmethod
    async def sign(self, data: bytes) -> bytes:
        """Sign data and return signature."""
        pass

    @abstractmethod
    async def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify signature on data."""
        pass


class PrivacyConnector(TrustConnector):
    """Base class for privacy mode connectors."""

    @abstractmethod
    async def generate_receipt(
        self,
        operation: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a privacy receipt for an operation."""
        pass

    @abstractmethod
    async def validate_receipt(self, receipt: Dict[str, Any]) -> bool:
        """Validate a privacy receipt."""
        pass

    @abstractmethod
    def is_safe_log_entry(self, log_entry: str) -> bool:
        """Check if a log entry complies with safe logging policy."""
        pass
