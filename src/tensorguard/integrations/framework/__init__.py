"""
TensorGuardFlow Integration Framework

This module provides the core infrastructure for integrating TGF with external systems:
- Connector contracts and base classes
- Configuration schemas (Pydantic models)
- Integration manager for tenant-specific configurations
- Topology model for visualization and auditing
"""

from tensorguard.integrations.framework.contracts import (
    IntegrationConnector,
    ConnectorCapability,
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.framework.config_schema import (
    IntegrationCategory,
    CategoryName,
    NodeStatus,
    EdgeProtocol,
    # Data source configs
    S3DataSourceConfig,
    GCSDataSourceConfig,
    AzureBlobDataSourceConfig,
    LocalDataSourceConfig,
    HFDatasetConfig,
    # Training configs
    LocalGPUConfig,
    K8sJobConfig,
    SageMakerJobConfig,
    VertexAIJobConfig,
    AzureMLJobConfig,
    DatabricksJobConfig,
    # Tracking configs
    MLflowConfig,
    WandBConfig,
    # Serving configs
    VLLMServingConfig,
    TGIServingConfig,
    TritonServingConfig,
    SageMakerEndpointConfig,
    # Trust configs
    AWSKMSConfig,
    VaultTransitConfig,
    NitroEnclaveConfig,
    N2HEConfig,
    # Base config
    IntegrationConfig,
)
from tensorguard.integrations.framework.topology import (
    IntegrationNode,
    IntegrationEdge,
    TopologySummary,
    IntegrationTopology,
    TopologyBuilder,
    EndpointUsage,
    ArtifactInfo,
)
from tensorguard.integrations.framework.manager import (
    IntegrationManager,
    IntegrationRegistry,
)

__all__ = [
    # Contracts
    "IntegrationConnector",
    "ConnectorCapability",
    "HealthCheckResult",
    "ValidationResult",
    "SmokeTestResult",
    "ExportArtifact",
    # Enums
    "IntegrationCategory",
    "CategoryName",
    "NodeStatus",
    "EdgeProtocol",
    # Data configs
    "S3DataSourceConfig",
    "GCSDataSourceConfig",
    "AzureBlobDataSourceConfig",
    "LocalDataSourceConfig",
    "HFDatasetConfig",
    # Training configs
    "LocalGPUConfig",
    "K8sJobConfig",
    "SageMakerJobConfig",
    "VertexAIJobConfig",
    "AzureMLJobConfig",
    "DatabricksJobConfig",
    # Tracking configs
    "MLflowConfig",
    "WandBConfig",
    # Serving configs
    "VLLMServingConfig",
    "TGIServingConfig",
    "TritonServingConfig",
    "SageMakerEndpointConfig",
    # Trust configs
    "AWSKMSConfig",
    "VaultTransitConfig",
    "NitroEnclaveConfig",
    "N2HEConfig",
    # Base config
    "IntegrationConfig",
    # Topology
    "IntegrationNode",
    "IntegrationEdge",
    "TopologySummary",
    "IntegrationTopology",
    "TopologyBuilder",
    "EndpointUsage",
    "ArtifactInfo",
    # Manager
    "IntegrationManager",
    "IntegrationRegistry",
]
