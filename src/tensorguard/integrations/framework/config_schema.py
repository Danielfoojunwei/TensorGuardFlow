"""
Configuration schemas for TensorGuardFlow integrations.

This module defines Pydantic models for all integration configurations,
organized by category (C/D/E/F/G as defined in the value chain).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
import hashlib
import json


class IntegrationCategory(str, Enum):
    """Integration categories mapping to value chain stages."""
    C = "C"  # Data Sources
    D = "D"  # Training Execution
    E = "E"  # Eval / Registry
    F = "F"  # Serving / Inference
    G = "G"  # Trust & Privacy


class CategoryName(str, Enum):
    """Human-readable category names."""
    DATA = "data"
    TRAINING = "training"
    EVAL_REGISTRY = "eval_registry"
    SERVING = "serving"
    TRUST_PRIVACY = "trust_privacy"


CATEGORY_TO_NAME = {
    IntegrationCategory.C: CategoryName.DATA,
    IntegrationCategory.D: CategoryName.TRAINING,
    IntegrationCategory.E: CategoryName.EVAL_REGISTRY,
    IntegrationCategory.F: CategoryName.SERVING,
    IntegrationCategory.G: CategoryName.TRUST_PRIVACY,
}


class NodeStatus(str, Enum):
    """Health status for integration nodes."""
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    DISABLED = "DISABLED"


class EdgeProtocol(str, Enum):
    """Types of connections between nodes."""
    EXPORT = "export"
    API = "api"
    FILE = "file"
    STREAM = "stream"
    WEBHOOK = "webhook"


class EdgeStatus(str, Enum):
    """Status of edges between nodes."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"


class EdgeDirection(str, Enum):
    """Direction of data flow."""
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"


class EndpointType(str, Enum):
    """Whether TGF calls or exposes the endpoint."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class EndpointProtocol(str, Enum):
    """Communication protocols."""
    HTTPS = "https"
    GRPC = "grpc"
    FILE = "file"
    S3 = "s3"
    GCS = "gcs"


class AuthMethod(str, Enum):
    """Authentication methods."""
    NONE = "none"
    API_KEY = "api_key"
    OAUTH = "oauth"
    IAM = "iam"
    MTLS = "mtls"


class ArtifactType(str, Enum):
    """Artifact formats."""
    YAML = "yaml"
    JSON = "json"
    PBTXT = "pbtxt"
    TAR = "tar"
    ZIP = "zip"


class OverallHealth(str, Enum):
    """Aggregate health status."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


# =============================================================================
# CATEGORY C: Data Source Configurations
# =============================================================================

class S3DataSourceConfig(BaseModel):
    """AWS S3 data source configuration."""
    bucket: str
    prefix: str = ""
    region: str = "us-east-1"
    role_arn: Optional[str] = None  # For cross-account access
    endpoint_url: Optional[str] = None  # For S3-compatible stores

    def get_provider_display(self) -> str:
        return "AWS S3"

    def compute_fingerprint(self) -> str:
        """Compute deterministic hash of configuration."""
        data = {
            "bucket": self.bucket,
            "prefix": self.prefix,
            "region": self.region,
            "role_arn": self.role_arn,
            "endpoint_url": self.endpoint_url,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class GCSDataSourceConfig(BaseModel):
    """Google Cloud Storage data source configuration."""
    bucket: str
    prefix: str = ""
    project_id: str
    credentials_path: Optional[str] = None

    def get_provider_display(self) -> str:
        return "Google Cloud Storage"

    def compute_fingerprint(self) -> str:
        data = {
            "bucket": self.bucket,
            "prefix": self.prefix,
            "project_id": self.project_id,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class AzureBlobDataSourceConfig(BaseModel):
    """Azure Blob Storage data source configuration."""
    storage_account: str
    container: str
    prefix: str = ""
    connection_string: Optional[str] = None
    sas_token: Optional[str] = None

    def get_provider_display(self) -> str:
        return "Azure Blob Storage"

    def compute_fingerprint(self) -> str:
        data = {
            "storage_account": self.storage_account,
            "container": self.container,
            "prefix": self.prefix,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class LocalDataSourceConfig(BaseModel):
    """Local filesystem data source configuration."""
    base_path: str
    glob_pattern: str = "**/*"
    follow_symlinks: bool = False

    def get_provider_display(self) -> str:
        return "Local Filesystem"

    def compute_fingerprint(self) -> str:
        data = {
            "base_path": self.base_path,
            "glob_pattern": self.glob_pattern,
            "follow_symlinks": self.follow_symlinks,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class HFDatasetConfig(BaseModel):
    """HuggingFace Datasets reference configuration."""
    dataset_id: str
    config_name: Optional[str] = None
    revision: str = "main"
    split: str = "train"
    token: Optional[str] = None  # For private datasets

    def get_provider_display(self) -> str:
        return "HuggingFace Datasets"

    def compute_fingerprint(self) -> str:
        data = {
            "dataset_id": self.dataset_id,
            "config_name": self.config_name,
            "revision": self.revision,
            "split": self.split,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


# =============================================================================
# CATEGORY D: Training Execution Configurations
# =============================================================================

class LocalGPUConfig(BaseModel):
    """Local GPU (CUDA) training configuration."""
    device_ids: List[int] = [0]
    mixed_precision: bool = True
    memory_fraction: float = Field(default=0.9, ge=0.1, le=1.0)

    def get_provider_display(self) -> str:
        return "Local GPU (CUDA)"

    def compute_fingerprint(self) -> str:
        data = {
            "device_ids": self.device_ids,
            "mixed_precision": self.mixed_precision,
            "memory_fraction": self.memory_fraction,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class K8sJobConfig(BaseModel):
    """Kubernetes Job training configuration."""
    namespace: str = "default"
    image: str
    gpu_count: int = Field(default=1, ge=0)
    cpu_request: str = "4"
    memory_request: str = "16Gi"
    data_pvc: Optional[str] = None
    output_pvc: Optional[str] = None
    service_account: Optional[str] = None
    node_selector: Dict[str, str] = {}
    tolerations: List[Dict[str, Any]] = []
    image_pull_secrets: List[str] = []

    def get_provider_display(self) -> str:
        return "Kubernetes"

    def compute_fingerprint(self) -> str:
        data = {
            "namespace": self.namespace,
            "image": self.image,
            "gpu_count": self.gpu_count,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class SageMakerJobConfig(BaseModel):
    """AWS SageMaker Training Job configuration."""
    role_arn: str
    instance_type: str = "ml.g5.xlarge"
    instance_count: int = 1
    volume_size_gb: int = 100
    max_runtime_seconds: int = 86400
    training_image: str
    data_s3_uri: str
    output_s3_uri: str
    vpc_config: Optional[Dict[str, Any]] = None
    enable_network_isolation: bool = False

    def get_provider_display(self) -> str:
        return "AWS SageMaker"

    def compute_fingerprint(self) -> str:
        data = {
            "role_arn": self.role_arn,
            "instance_type": self.instance_type,
            "training_image": self.training_image,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class VertexAIJobConfig(BaseModel):
    """Google Vertex AI Custom Job configuration."""
    project_id: str
    location: str = "us-central1"
    machine_type: str = "n1-standard-8"
    accelerator_type: str = "NVIDIA_TESLA_V100"
    accelerator_count: int = 1
    training_image: str
    staging_bucket: str

    def get_provider_display(self) -> str:
        return "Google Vertex AI"

    def compute_fingerprint(self) -> str:
        data = {
            "project_id": self.project_id,
            "location": self.location,
            "training_image": self.training_image,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class AzureMLJobConfig(BaseModel):
    """Azure Machine Learning Job configuration."""
    workspace_name: str
    resource_group: str
    subscription_id: str
    compute_target: str
    environment_name: str
    training_script: str
    data_uri: str
    output_uri: str

    def get_provider_display(self) -> str:
        return "Azure Machine Learning"

    def compute_fingerprint(self) -> str:
        data = {
            "workspace_name": self.workspace_name,
            "compute_target": self.compute_target,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class DatabricksJobConfig(BaseModel):
    """Databricks Job configuration."""
    workspace_url: str
    cluster_id: Optional[str] = None
    new_cluster: Optional[Dict[str, Any]] = None
    notebook_path: Optional[str] = None
    python_file: Optional[str] = None
    parameters: Dict[str, str] = {}

    def get_provider_display(self) -> str:
        return "Databricks"

    def compute_fingerprint(self) -> str:
        data = {
            "workspace_url": self.workspace_url,
            "cluster_id": self.cluster_id,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


# =============================================================================
# CATEGORY E: Eval / Tracking Configurations
# =============================================================================

class MLflowConfig(BaseModel):
    """MLflow tracking configuration."""
    tracking_uri: str
    experiment_name: str
    artifact_location: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

    def get_provider_display(self) -> str:
        return "MLflow"

    def compute_fingerprint(self) -> str:
        data = {
            "tracking_uri": self.tracking_uri,
            "experiment_name": self.experiment_name,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class WandBConfig(BaseModel):
    """Weights & Biases configuration."""
    api_key: str
    project: str
    entity: Optional[str] = None
    tags: List[str] = []

    def get_provider_display(self) -> str:
        return "Weights & Biases"

    def compute_fingerprint(self) -> str:
        data = {
            "project": self.project,
            "entity": self.entity,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


# =============================================================================
# CATEGORY F: Serving Configurations
# =============================================================================

class VLLMServingConfig(BaseModel):
    """vLLM serving configuration."""
    base_model: str
    tensor_parallel_size: int = 1
    max_model_len: int = 4096
    gpu_memory_utilization: float = Field(default=0.9, ge=0.1, le=1.0)
    adapter_path: Optional[str] = None
    resolve_endpoint: Optional[str] = None

    def get_provider_display(self) -> str:
        return "vLLM"

    def compute_fingerprint(self) -> str:
        data = {
            "base_model": self.base_model,
            "tensor_parallel_size": self.tensor_parallel_size,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class TGIServingConfig(BaseModel):
    """Text Generation Inference (TGI) serving configuration."""
    base_model: str
    max_input_length: int = 1024
    max_total_tokens: int = 2048
    quantize: Optional[str] = None
    adapter_path: Optional[str] = None
    resolve_endpoint: Optional[str] = None

    def get_provider_display(self) -> str:
        return "Text Generation Inference (TGI)"

    def compute_fingerprint(self) -> str:
        data = {
            "base_model": self.base_model,
            "max_total_tokens": self.max_total_tokens,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class TritonServingConfig(BaseModel):
    """NVIDIA Triton Inference Server configuration."""
    model_name: str
    max_batch_size: int = 8
    instance_count: int = 1
    adapter_path: Optional[str] = None
    resolve_endpoint: Optional[str] = None

    def get_provider_display(self) -> str:
        return "NVIDIA Triton"

    def compute_fingerprint(self) -> str:
        data = {
            "model_name": self.model_name,
            "max_batch_size": self.max_batch_size,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class SageMakerEndpointConfig(BaseModel):
    """AWS SageMaker Endpoint configuration (template export only)."""
    role_arn: str
    instance_type: str = "ml.g5.xlarge"
    initial_instance_count: int = 1
    model_data_url: str
    inference_image: str

    def get_provider_display(self) -> str:
        return "AWS SageMaker Endpoint"

    def compute_fingerprint(self) -> str:
        data = {
            "role_arn": self.role_arn,
            "instance_type": self.instance_type,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


# =============================================================================
# CATEGORY G: Trust & Privacy Configurations
# =============================================================================

class AWSKMSConfig(BaseModel):
    """AWS KMS signing configuration."""
    key_id: str  # Key ID, ARN, or alias
    region: str = "us-east-1"
    signing_algorithm: str = "RSASSA_PSS_SHA_256"
    role_arn: Optional[str] = None  # For cross-account

    def get_provider_display(self) -> str:
        return "AWS KMS"

    def compute_fingerprint(self) -> str:
        data = {
            "key_id": self.key_id,
            "region": self.region,
            "signing_algorithm": self.signing_algorithm,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class VaultTransitConfig(BaseModel):
    """HashiCorp Vault Transit configuration."""
    vault_addr: str
    token: Optional[str] = None
    transit_mount: str = "transit"
    key_name: str
    auth_method: str = "token"
    auth_config: Dict[str, str] = {}

    def get_provider_display(self) -> str:
        return "HashiCorp Vault"

    def compute_fingerprint(self) -> str:
        data = {
            "vault_addr": self.vault_addr,
            "key_name": self.key_name,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class NitroEnclaveConfig(BaseModel):
    """AWS Nitro Enclave configuration."""
    enclave_cid: int
    vsock_port: int = 5000
    pcr_values: Dict[int, str] = {}  # Expected PCR values
    kms_key_id: str

    def get_provider_display(self) -> str:
        return "AWS Nitro Enclaves"

    def compute_fingerprint(self) -> str:
        data = {
            "enclave_cid": self.enclave_cid,
            "kms_key_id": self.kms_key_id,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


class N2HEConfig(BaseModel):
    """N2HE Privacy Mode configuration."""
    enabled: bool = False
    encryption_mode: str = "FULL"  # FULL, METADATA_ONLY
    receipt_generation: bool = True
    safe_logging: bool = True
    receipt_retention_days: int = 90

    def get_provider_display(self) -> str:
        return "N2HE Privacy Mode"

    def compute_fingerprint(self) -> str:
        data = {
            "enabled": self.enabled,
            "encryption_mode": self.encryption_mode,
            "receipt_generation": self.receipt_generation,
        }
        serialized = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


# =============================================================================
# Generic Integration Configuration
# =============================================================================

# Type alias for all config types
DataSourceConfigType = Union[
    S3DataSourceConfig,
    GCSDataSourceConfig,
    AzureBlobDataSourceConfig,
    LocalDataSourceConfig,
    HFDatasetConfig,
]

TrainingConfigType = Union[
    LocalGPUConfig,
    K8sJobConfig,
    SageMakerJobConfig,
    VertexAIJobConfig,
    AzureMLJobConfig,
    DatabricksJobConfig,
]

TrackingConfigType = Union[MLflowConfig, WandBConfig]

ServingConfigType = Union[
    VLLMServingConfig,
    TGIServingConfig,
    TritonServingConfig,
    SageMakerEndpointConfig,
]

TrustConfigType = Union[
    AWSKMSConfig,
    VaultTransitConfig,
    NitroEnclaveConfig,
    N2HEConfig,
]

AllConfigTypes = Union[
    DataSourceConfigType,
    TrainingConfigType,
    TrackingConfigType,
    ServingConfigType,
    TrustConfigType,
]


class IntegrationConfig(BaseModel):
    """Generic integration configuration wrapper."""
    id: str
    category: IntegrationCategory
    provider: str
    enabled: bool = True
    config: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def compute_fingerprint(self) -> str:
        """Compute deterministic hash of configuration."""
        data = {
            "category": self.category.value,
            "provider": self.provider,
            "config": self.config,
        }
        serialized = json.dumps(data, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


# Provider registry mapping
PROVIDER_REGISTRY = {
    # Category C: Data
    "aws_s3": (IntegrationCategory.C, S3DataSourceConfig),
    "gcs": (IntegrationCategory.C, GCSDataSourceConfig),
    "azure_blob": (IntegrationCategory.C, AzureBlobDataSourceConfig),
    "local_fs": (IntegrationCategory.C, LocalDataSourceConfig),
    "hf_datasets": (IntegrationCategory.C, HFDatasetConfig),
    # Category D: Training
    "cuda_local": (IntegrationCategory.D, LocalGPUConfig),
    "kubernetes": (IntegrationCategory.D, K8sJobConfig),
    "sagemaker": (IntegrationCategory.D, SageMakerJobConfig),
    "vertex_ai": (IntegrationCategory.D, VertexAIJobConfig),
    "azure_ml": (IntegrationCategory.D, AzureMLJobConfig),
    "databricks": (IntegrationCategory.D, DatabricksJobConfig),
    # Category E: Tracking
    "mlflow": (IntegrationCategory.E, MLflowConfig),
    "wandb": (IntegrationCategory.E, WandBConfig),
    # Category F: Serving
    "vllm": (IntegrationCategory.F, VLLMServingConfig),
    "tgi": (IntegrationCategory.F, TGIServingConfig),
    "triton": (IntegrationCategory.F, TritonServingConfig),
    "sagemaker_endpoint": (IntegrationCategory.F, SageMakerEndpointConfig),
    # Category G: Trust
    "aws_kms": (IntegrationCategory.G, AWSKMSConfig),
    "vault_transit": (IntegrationCategory.G, VaultTransitConfig),
    "nitro_enclave": (IntegrationCategory.G, NitroEnclaveConfig),
    "n2he": (IntegrationCategory.G, N2HEConfig),
}


def get_config_class(provider: str):
    """Get the configuration class for a provider."""
    if provider not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}")
    return PROVIDER_REGISTRY[provider][1]


def get_category_for_provider(provider: str) -> IntegrationCategory:
    """Get the category for a provider."""
    if provider not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}")
    return PROVIDER_REGISTRY[provider][0]
