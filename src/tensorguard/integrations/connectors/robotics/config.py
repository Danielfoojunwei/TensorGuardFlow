"""
Configuration schemas for TensorGuardFlow Robotics Ops Connectors.

This module defines Pydantic models for connector configurations,
supporting InOrbit, Formant, Foxglove, and generic webhook providers.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import hashlib
import json


# =============================================================================
# ENUMS
# =============================================================================

class RoboticsProvider(str, Enum):
    """Supported robotics ops providers."""
    INORBIT = "inorbit"
    FORMANT = "formant"
    FOXGLOVE = "foxglove"
    GENERIC = "generic"


class OutboundMode(str, Enum):
    """Mode for outbound event delivery."""
    WEBHOOK = "webhook"      # POST to webhook URL
    API = "api"              # Use provider's API
    SDK = "sdk"              # Use provider's SDK (if available)


class AuthType(str, Enum):
    """Authentication types for outbound requests."""
    NONE = "none"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH = "oauth"
    HMAC = "hmac"


# =============================================================================
# RETRY POLICY
# =============================================================================

class RetryPolicy(BaseModel):
    """Configuration for retry behavior."""
    max_retries: int = Field(
        default=10,
        ge=0,
        le=20,
        description="Maximum number of retry attempts"
    )
    initial_delay_ms: int = Field(
        default=1000,
        ge=100,
        le=60000,
        description="Initial delay before first retry (ms)"
    )
    max_delay_ms: int = Field(
        default=60000,
        ge=1000,
        le=600000,
        description="Maximum delay between retries (ms)"
    )
    exponential_base: float = Field(
        default=2.0,
        ge=1.1,
        le=4.0,
        description="Base for exponential backoff"
    )
    retry_on_status_codes: List[int] = Field(
        default=[429, 500, 502, 503, 504],
        description="HTTP status codes to retry on"
    )

    def get_delay_ms(self, attempt: int) -> int:
        """Calculate delay for a given attempt number."""
        delay = self.initial_delay_ms * (self.exponential_base ** attempt)
        return min(int(delay), self.max_delay_ms)


# =============================================================================
# OUTBOUND CONFIGURATION
# =============================================================================

class OutboundConfig(BaseModel):
    """Configuration for outbound event delivery."""
    mode: OutboundMode = Field(
        default=OutboundMode.WEBHOOK,
        description="Delivery mode: webhook, api, or sdk"
    )
    target_url: Optional[str] = Field(
        default=None,
        description="Target URL for webhook mode"
    )
    api_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for API mode"
    )
    auth_type: AuthType = Field(
        default=AuthType.BEARER,
        description="Authentication type"
    )
    secret_ref: Optional[str] = Field(
        default=None,
        description="Reference to secret in KMS/vault (DO NOT store actual secret)"
    )
    timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=120000,
        description="Request timeout in milliseconds"
    )
    retry_policy: RetryPolicy = Field(
        default_factory=RetryPolicy,
        description="Retry policy for failed deliveries"
    )
    rate_limit_qps: float = Field(
        default=10.0,
        ge=0.1,
        le=1000.0,
        description="Rate limit in queries per second"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional headers to include in requests"
    )

    @field_validator("target_url", "api_base_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


# =============================================================================
# INBOUND CONFIGURATION
# =============================================================================

class ReplayProtectionConfig(BaseModel):
    """Configuration for replay attack protection."""
    window_sec: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Time window for accepting signals (seconds)"
    )
    dedupe_cache_size: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum number of dedupe keys to cache"
    )


class InboundConfig(BaseModel):
    """Configuration for inbound webhook handling."""
    webhook_path: str = Field(
        default="/robotics/webhook/{provider}",
        description="Path for receiving webhooks (TGF server)"
    )
    verify_signature: bool = Field(
        default=True,
        description="Whether to verify webhook signatures"
    )
    signature_header_name: str = Field(
        default="X-Signature",
        description="Header name containing the signature"
    )
    signing_secret_ref: Optional[str] = Field(
        default=None,
        description="Reference to signing secret in KMS/vault"
    )
    public_key_ref: Optional[str] = Field(
        default=None,
        description="Reference to public key for asymmetric verification"
    )
    timestamp_header_name: Optional[str] = Field(
        default=None,
        description="Header name containing timestamp (for freshness check)"
    )
    replay_protection: ReplayProtectionConfig = Field(
        default_factory=ReplayProtectionConfig,
        description="Replay protection configuration"
    )
    allowed_source_ips: Optional[List[str]] = Field(
        default=None,
        description="IP whitelist for additional security (CIDR notation)"
    )


# =============================================================================
# MAPPING CONFIGURATION
# =============================================================================

class SeverityMapping(BaseModel):
    """Mapping from provider severity to TGF severity."""
    critical: List[str] = Field(
        default=["critical", "emergency", "fatal", "high", "p1"],
        description="Provider values that map to CRITICAL"
    )
    warn: List[str] = Field(
        default=["warning", "warn", "medium", "p2", "p3"],
        description="Provider values that map to WARN"
    )
    info: List[str] = Field(
        default=["info", "low", "p4", "p5"],
        description="Provider values that map to INFO"
    )


class EventTypeMapping(BaseModel):
    """Mapping from provider event types to TGF signal types."""
    safety_stop: List[str] = Field(
        default=["robot.safety.triggered", "emergency_stop", "safety_violation"],
        description="Event types that map to safety_stop"
    )
    regression_detected: List[str] = Field(
        default=["performance.regression", "metric.degradation"],
        description="Event types that map to regression_detected"
    )
    task_failure_spike: List[str] = Field(
        default=["task.failure.spike", "error_rate.high"],
        description="Event types that map to task_failure_spike"
    )
    # Add more mappings as needed


class MappingConfig(BaseModel):
    """Configuration for event/signal type mappings."""
    default_route_key: Optional[str] = Field(
        default=None,
        description="Default route key if not specified in signal"
    )
    severity_mapping: SeverityMapping = Field(
        default_factory=SeverityMapping,
        description="Severity value mappings"
    )
    event_type_mapping: EventTypeMapping = Field(
        default_factory=EventTypeMapping,
        description="Event type mappings"
    )
    tenant_id_field: str = Field(
        default="tenant_id",
        description="Field name for tenant ID in incoming signals"
    )
    route_key_field: str = Field(
        default="route_key",
        description="Field name for route key in incoming signals"
    )


# =============================================================================
# N2HE PRIVACY CONFIGURATION
# =============================================================================

class N2HEIntegrationConfig(BaseModel):
    """N2HE privacy mode configuration for robotics integrations."""
    enabled: bool = Field(
        default=False,
        description="Enable N2HE privacy mode"
    )
    redact_identifiers_in_logs: bool = Field(
        default=True,
        description="Redact tenant/route identifiers in logs"
    )
    encrypt_stored_payloads: bool = Field(
        default=True,
        description="Encrypt raw payloads before storage"
    )
    privacy_overhead_tracking: bool = Field(
        default=True,
        description="Track privacy mode overhead metrics"
    )


# =============================================================================
# DLQ CONFIGURATION
# =============================================================================

class DLQConfig(BaseModel):
    """Dead Letter Queue configuration."""
    enabled: bool = Field(
        default=True,
        description="Enable DLQ for failed deliveries"
    )
    max_entries: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum DLQ entries before oldest are evicted"
    )
    retention_hours: int = Field(
        default=72,
        ge=1,
        le=720,
        description="How long to retain DLQ entries"
    )
    auto_retry_enabled: bool = Field(
        default=True,
        description="Enable automatic retry of DLQ entries"
    )
    auto_retry_interval_sec: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Interval between auto-retry attempts"
    )


# =============================================================================
# PROVIDER-SPECIFIC CONFIGURATIONS
# =============================================================================

class InOrbitConfig(BaseModel):
    """InOrbit-specific configuration."""
    organization_id: Optional[str] = Field(
        default=None,
        description="InOrbit organization ID"
    )
    api_version: str = Field(
        default="v1",
        description="API version to use"
    )
    robot_id_field: str = Field(
        default="robotId",
        description="Field name for robot ID in payloads"
    )
    signature_header: str = Field(
        default="X-InOrbit-Signature",
        description="Signature header name"
    )


class FormantConfig(BaseModel):
    """Formant-specific configuration."""
    organization_id: Optional[str] = Field(
        default=None,
        description="Formant organization ID"
    )
    api_version: str = Field(
        default="v1",
        description="API version to use"
    )
    device_id_field: str = Field(
        default="deviceId",
        description="Field name for device ID in payloads"
    )
    signature_header: str = Field(
        default="X-Formant-Signature",
        description="Signature header name"
    )
    supports_acknowledgment: bool = Field(
        default=True,
        description="Whether to send acknowledgment callbacks"
    )


class FoxgloveConfig(BaseModel):
    """Foxglove-specific configuration."""
    organization_id: Optional[str] = Field(
        default=None,
        description="Foxglove organization ID"
    )
    enable_mcap_export: bool = Field(
        default=True,
        description="Enable MCAP bundle pointer export"
    )
    mcap_storage_base: Optional[str] = Field(
        default=None,
        description="Base path/URL for MCAP storage"
    )
    signature_header: str = Field(
        default="X-Foxglove-Signature",
        description="Signature header name"
    )


# =============================================================================
# MAIN CONNECTOR CONFIGURATION
# =============================================================================

class RoboticsConnectorConfig(BaseModel):
    """
    Complete configuration for a robotics ops connector.

    This is the main configuration schema used when configuring
    InOrbit, Formant, Foxglove, or generic connectors.
    """
    # Provider identification
    provider: RoboticsProvider = Field(
        description="Provider type: inorbit, formant, foxglove, generic"
    )
    enabled: bool = Field(
        default=True,
        description="Whether this connector is enabled"
    )
    display_name: Optional[str] = Field(
        default=None,
        description="Human-readable display name"
    )

    # Communication configuration
    outbound: OutboundConfig = Field(
        default_factory=OutboundConfig,
        description="Outbound event delivery configuration"
    )
    inbound: InboundConfig = Field(
        default_factory=InboundConfig,
        description="Inbound webhook configuration"
    )

    # Mapping configuration
    mapping: MappingConfig = Field(
        default_factory=MappingConfig,
        description="Event/signal type mappings"
    )

    # Privacy configuration
    n2he: N2HEIntegrationConfig = Field(
        default_factory=N2HEIntegrationConfig,
        description="N2HE privacy mode configuration"
    )

    # DLQ configuration
    dlq: DLQConfig = Field(
        default_factory=DLQConfig,
        description="Dead letter queue configuration"
    )

    # Provider-specific configuration
    inorbit: Optional[InOrbitConfig] = Field(
        default=None,
        description="InOrbit-specific settings"
    )
    formant: Optional[FormantConfig] = Field(
        default=None,
        description="Formant-specific settings"
    )
    foxglove: Optional[FoxgloveConfig] = Field(
        default=None,
        description="Foxglove-specific settings"
    )

    # Metadata
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom tags for organization"
    )

    def get_display_name(self) -> str:
        """Get display name or generate from provider."""
        if self.display_name:
            return self.display_name
        return f"{self.provider.value.title()} Integration"

    def compute_fingerprint(self) -> str:
        """Compute deterministic hash of configuration (excluding secrets)."""
        # Create a copy without secret references
        safe_dict = self.model_dump(exclude_none=True)

        # Remove secret references
        def remove_secrets(d: dict) -> dict:
            result = {}
            for k, v in d.items():
                if "secret" in k.lower() or "key" in k.lower():
                    continue
                elif isinstance(v, dict):
                    result[k] = remove_secrets(v)
                else:
                    result[k] = v
            return result

        safe_dict = remove_secrets(safe_dict)
        serialized = json.dumps(safe_dict, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"

    def get_provider_config(self) -> Optional[BaseModel]:
        """Get provider-specific configuration."""
        if self.provider == RoboticsProvider.INORBIT:
            return self.inorbit
        elif self.provider == RoboticsProvider.FORMANT:
            return self.formant
        elif self.provider == RoboticsProvider.FOXGLOVE:
            return self.foxglove
        return None

    @field_validator("provider")
    @classmethod
    def validate_provider_config_present(cls, v: RoboticsProvider) -> RoboticsProvider:
        """Provider-specific config validation is done at model level."""
        return v

    def validate_complete(self) -> List[str]:
        """
        Validate configuration completeness.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        # Check outbound configuration
        if self.outbound.mode == OutboundMode.WEBHOOK:
            if not self.outbound.target_url:
                errors.append("outbound.target_url is required for webhook mode")
        elif self.outbound.mode == OutboundMode.API:
            if not self.outbound.api_base_url:
                errors.append("outbound.api_base_url is required for API mode")

        # Check authentication
        if self.outbound.auth_type != AuthType.NONE:
            if not self.outbound.secret_ref:
                errors.append("outbound.secret_ref is required when auth_type is not 'none'")

        # Check signature verification
        if self.inbound.verify_signature:
            if not self.inbound.signing_secret_ref and not self.inbound.public_key_ref:
                errors.append(
                    "inbound.signing_secret_ref or public_key_ref required when verify_signature=true"
                )

        return errors


# =============================================================================
# CONFIGURATION TEMPLATES
# =============================================================================

def get_inorbit_template() -> RoboticsConnectorConfig:
    """Get a template configuration for InOrbit."""
    return RoboticsConnectorConfig(
        provider=RoboticsProvider.INORBIT,
        display_name="InOrbit Fleet Management",
        outbound=OutboundConfig(
            mode=OutboundMode.API,
            api_base_url="https://api.inorbit.ai/v1",
            auth_type=AuthType.BEARER,
        ),
        inbound=InboundConfig(
            webhook_path="/robotics/webhook/inorbit",
            signature_header_name="X-InOrbit-Signature",
        ),
        inorbit=InOrbitConfig(),
    )


def get_formant_template() -> RoboticsConnectorConfig:
    """Get a template configuration for Formant."""
    return RoboticsConnectorConfig(
        provider=RoboticsProvider.FORMANT,
        display_name="Formant Robotics Platform",
        outbound=OutboundConfig(
            mode=OutboundMode.API,
            api_base_url="https://api.formant.io/v1",
            auth_type=AuthType.BEARER,
        ),
        inbound=InboundConfig(
            webhook_path="/robotics/webhook/formant",
            signature_header_name="X-Formant-Signature",
        ),
        formant=FormantConfig(),
    )


def get_foxglove_template() -> RoboticsConnectorConfig:
    """Get a template configuration for Foxglove."""
    return RoboticsConnectorConfig(
        provider=RoboticsProvider.FOXGLOVE,
        display_name="Foxglove Observability",
        outbound=OutboundConfig(
            mode=OutboundMode.WEBHOOK,
            auth_type=AuthType.BEARER,
        ),
        inbound=InboundConfig(
            webhook_path="/robotics/webhook/foxglove",
            signature_header_name="X-Foxglove-Signature",
        ),
        foxglove=FoxgloveConfig(),
    )


def get_generic_template() -> RoboticsConnectorConfig:
    """Get a template configuration for generic webhook provider."""
    return RoboticsConnectorConfig(
        provider=RoboticsProvider.GENERIC,
        display_name="Generic Webhook",
        outbound=OutboundConfig(
            mode=OutboundMode.WEBHOOK,
            auth_type=AuthType.NONE,
        ),
        inbound=InboundConfig(
            webhook_path="/robotics/webhook/generic",
            verify_signature=False,
        ),
    )
