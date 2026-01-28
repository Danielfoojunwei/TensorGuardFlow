"""
TensorGuardFlow Robotics Ops Integrations.

This module provides connectors for external robotics operations platforms:
- InOrbit: Fleet management and monitoring
- Formant: Robotics platform with incident management
- Foxglove: Visualization and recording platform

These integrations enable:
- Outbound events: Notify ops tools of TGF events (promotions, rollbacks, etc.)
- Inbound signals: Receive incidents/alerts that trigger TGF actions
"""

from tensorguard.integrations.connectors.robotics.schemas import (
    # Enums
    Severity,
    EventCategory,
    OutboundEventType,
    SignalSource,
    InboundSignalType,
    ActionType,
    # Outbound Events
    OutboundOpsEvent,
    EventPayload,
    EvidenceRefs,
    ActionContext,
    # Inbound Signals
    InboundOpsSignal,
    SignalPayload,
    NormalizedSignalData,
    ThresholdViolation,
    AuthInfo,
    # Results
    SendResult,
    IngestResult,
    # Mapping
    DEFAULT_SIGNAL_ACTION_MAP,
    get_default_action_for_signal,
)

from tensorguard.integrations.connectors.robotics.base import (
    RoboticsOpsConnector,
    RoboticsOpsCapability,
    BoundedDedupeCache,
    verify_hmac_signature,
)

from tensorguard.integrations.connectors.robotics.config import (
    RoboticsProvider,
    RoboticsConnectorConfig,
    OutboundMode,
    AuthType,
    RetryPolicy,
    OutboundConfig,
    InboundConfig,
    ReplayProtectionConfig,
    DLQConfig,
    get_inorbit_template,
    get_formant_template,
    get_foxglove_template,
    get_generic_template,
)

from tensorguard.integrations.connectors.robotics.inorbit_connector import (
    InOrbitConnector,
)
from tensorguard.integrations.connectors.robotics.formant_connector import (
    FormantConnector,
)
from tensorguard.integrations.connectors.robotics.foxglove_connector import (
    FoxgloveConnector,
)

__all__ = [
    # Enums
    "Severity",
    "EventCategory",
    "OutboundEventType",
    "SignalSource",
    "InboundSignalType",
    "ActionType",
    # Outbound Events
    "OutboundOpsEvent",
    "EventPayload",
    "EvidenceRefs",
    "ActionContext",
    # Inbound Signals
    "InboundOpsSignal",
    "SignalPayload",
    "NormalizedSignalData",
    "ThresholdViolation",
    "AuthInfo",
    # Results
    "SendResult",
    "IngestResult",
    # Mapping
    "DEFAULT_SIGNAL_ACTION_MAP",
    "get_default_action_for_signal",
    # Base classes
    "RoboticsOpsConnector",
    "RoboticsOpsCapability",
    "BoundedDedupeCache",
    "verify_hmac_signature",
    # Config
    "RoboticsProvider",
    "RoboticsConnectorConfig",
    "OutboundMode",
    "AuthType",
    "RetryPolicy",
    "OutboundConfig",
    "InboundConfig",
    "ReplayProtectionConfig",
    "DLQConfig",
    "get_inorbit_template",
    "get_formant_template",
    "get_foxglove_template",
    "get_generic_template",
    # Connectors
    "InOrbitConnector",
    "FormantConnector",
    "FoxgloveConnector",
]
