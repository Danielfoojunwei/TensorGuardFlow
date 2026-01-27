"""
Integration connectors for TensorGuardFlow.

This module provides connector implementations for all supported external systems,
organized by category (C/D/E/F/G as defined in the value chain).
"""

from tensorguard.integrations.connectors.data_sources import (
    LocalFilesystemConnector,
    S3Connector,
)
from tensorguard.integrations.connectors.training import (
    LocalGPUConnector,
    KubernetesConnector,
)
from tensorguard.integrations.connectors.tracking import (
    TGFInternalRegistryConnector,
    MLflowConnector,
)
from tensorguard.integrations.connectors.serving import (
    VLLMConnector,
    TGIConnector,
    TritonConnector,
)
from tensorguard.integrations.connectors.trust import (
    AWSKMSConnector,
    N2HEConnector,
    LocalDevSigningConnector,
)

__all__ = [
    # Data sources (C)
    "LocalFilesystemConnector",
    "S3Connector",
    # Training (D)
    "LocalGPUConnector",
    "KubernetesConnector",
    # Tracking (E)
    "TGFInternalRegistryConnector",
    "MLflowConnector",
    # Serving (F)
    "VLLMConnector",
    "TGIConnector",
    "TritonConnector",
    # Trust (G)
    "AWSKMSConnector",
    "N2HEConnector",
    "LocalDevSigningConnector",
]
