"""
TensorGuard Integrations Package

Provides integration capabilities for external systems across the ML lifecycle:
- Category C: Data Sources (S3, local filesystem)
- Category D: Training (K8s, local GPU, SageMaker, Vertex AI, Azure ML, Databricks)
- Category E: Tracking/Registry (TGF Internal, MLflow, W&B)
- Category F: Serving (vLLM, TGI, Triton)
- Category G: Trust/Privacy (AWS KMS, N2HE)
"""
from .rmf.adapter import RmfAdapter
from .vda5050.bridge import Vda5050Bridge

# Import new connector framework
from .connectors import (
    LocalFilesystemConnector,
    S3Connector,
    LocalGPUConnector,
    KubernetesConnector,
    TGFInternalRegistryConnector,
    MLflowConnector,
    VLLMConnector,
    TGIConnector,
    TritonConnector,
    AWSKMSConnector,
    N2HEConnector,
    LocalDevSigningConnector,
)

# Import exporters
from .exporters import (
    VLLMExporter,
    TGIExporter,
    TritonExporter,
    SageMakerExporter,
    VertexAIExporter,
    AzureMLExporter,
    DatabricksExporter,
    SageMakerEndpointExporter,
)

# Import framework components
from .framework import (
    IntegrationManager,
    IntegrationRegistry,
    TopologyBuilder,
    IntegrationTopology,
)

__all__ = [
    # Legacy adapters
    "RmfAdapter",
    "Vda5050Bridge",
    # Data source connectors
    "LocalFilesystemConnector",
    "S3Connector",
    # Training connectors
    "LocalGPUConnector",
    "KubernetesConnector",
    # Tracking connectors
    "TGFInternalRegistryConnector",
    "MLflowConnector",
    # Serving connectors
    "VLLMConnector",
    "TGIConnector",
    "TritonConnector",
    # Trust connectors
    "AWSKMSConnector",
    "N2HEConnector",
    "LocalDevSigningConnector",
    # Exporters
    "VLLMExporter",
    "TGIExporter",
    "TritonExporter",
    "SageMakerExporter",
    "VertexAIExporter",
    "AzureMLExporter",
    "DatabricksExporter",
    "SageMakerEndpointExporter",
    # Framework
    "IntegrationManager",
    "IntegrationRegistry",
    "TopologyBuilder",
    "IntegrationTopology",
]
