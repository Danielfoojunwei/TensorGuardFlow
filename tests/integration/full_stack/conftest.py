"""
Shared fixtures for full-stack integration tests.

Provides fixtures for:
- Integration manager instances
- Mock connector configurations
- Exporter test contexts
"""

import os
import tempfile
import pytest
from typing import Dict, Any

# Ensure development environment
os.environ.setdefault("TG_ENVIRONMENT", "development")
os.environ.setdefault("TG_ENABLE_REMOTE_SUBMIT", "false")


@pytest.fixture
def local_data_config() -> Dict[str, Any]:
    """Configuration for local filesystem data source."""
    return {
        "base_path": tempfile.mkdtemp(prefix="tgf_test_data_"),
        "allowed_extensions": [".json", ".jsonl", ".csv", ".parquet"],
    }


@pytest.fixture
def local_gpu_config() -> Dict[str, Any]:
    """Configuration for local GPU training connector."""
    return {
        "max_concurrent_jobs": 1,
        "default_timeout_seconds": 3600,
        "gpu_ids": [],  # Empty for CPU-only testing
    }


@pytest.fixture
def vllm_exporter_config() -> Dict[str, Any]:
    """Configuration for vLLM exporter."""
    return {
        "base_model": "meta-llama/Llama-2-7b-hf",
        "tensor_parallel_size": 1,
        "max_model_len": 4096,
        "gpu_memory_utilization": 0.9,
        "resolve_endpoint": "/tgflow/resolve",
    }


@pytest.fixture
def tgi_exporter_config() -> Dict[str, Any]:
    """Configuration for TGI exporter."""
    return {
        "base_model": "meta-llama/Llama-2-7b-hf",
        "max_input_length": 1024,
        "max_total_tokens": 2048,
        "quantize": None,
        "resolve_endpoint": "/tgflow/resolve",
    }


@pytest.fixture
def triton_exporter_config() -> Dict[str, Any]:
    """Configuration for Triton exporter."""
    return {
        "model_name": "llama2_7b",
        "max_batch_size": 8,
        "instance_count": 1,
        "resolve_endpoint": "/tgflow/resolve",
    }


@pytest.fixture
def sagemaker_training_config() -> Dict[str, Any]:
    """Configuration for SageMaker training exporter."""
    return {
        "role_arn": "arn:aws:iam::123456789012:role/SageMakerRole",
        "training_image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/tgf-training:latest",
        "data_s3_uri": "s3://tgf-test-bucket/data/",
        "output_s3_uri": "s3://tgf-test-bucket/output/",
        "instance_type": "ml.g5.xlarge",
        "instance_count": 1,
        "volume_size_gb": 100,
    }


@pytest.fixture
def sagemaker_endpoint_config() -> Dict[str, Any]:
    """Configuration for SageMaker endpoint exporter."""
    return {
        "role_arn": "arn:aws:iam::123456789012:role/SageMakerRole",
        "inference_image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/tgf-inference:latest",
        "instance_type": "ml.g5.xlarge",
        "initial_instance_count": 1,
        "resolve_endpoint": "/tgflow/resolve",
    }


@pytest.fixture
def vertex_ai_config() -> Dict[str, Any]:
    """Configuration for Vertex AI exporter."""
    return {
        "project_id": "tgf-test-project",
        "location": "us-central1",
        "training_image": "gcr.io/tgf-test-project/tgf-training:latest",
        "machine_type": "n1-standard-8",
        "accelerator_type": "NVIDIA_TESLA_V100",
        "accelerator_count": 1,
    }


@pytest.fixture
def azure_ml_config() -> Dict[str, Any]:
    """Configuration for Azure ML exporter."""
    return {
        "workspace_name": "tgf-workspace",
        "resource_group": "tgf-resource-group",
        "compute_target": "gpu-cluster",
        "environment_name": "AzureML-pytorch-1.13-cuda11.7-cudnn8-devel",
        "code_path": "./src",
        "command": "python train.py",
    }


@pytest.fixture
def databricks_config() -> Dict[str, Any]:
    """Configuration for Databricks exporter."""
    return {
        "workspace_url": "https://adb-1234567890123456.7.azuredatabricks.net",
        "cluster_id": "0101-120000-abcde123",
        "notebook_path": "/Shared/tgf/training",
    }


@pytest.fixture
def k8s_job_config() -> Dict[str, Any]:
    """Configuration for Kubernetes job exporter."""
    return {
        "namespace": "tgf-training",
        "image": "tgf/training:latest",
        "service_account": "tgf-training-sa",
        "cpu_request": "4",
        "cpu_limit": "8",
        "memory_request": "16Gi",
        "memory_limit": "32Gi",
        "gpu_count": 1,
    }


@pytest.fixture
def aws_kms_config() -> Dict[str, Any]:
    """Configuration for AWS KMS connector (test mode)."""
    return {
        "region": "us-east-1",
        "key_id": "alias/tgf-signing-key",
        "endpoint_url": None,  # Use default
    }


@pytest.fixture
def n2he_config() -> Dict[str, Any]:
    """Configuration for N2HE privacy connector."""
    return {
        "enabled": True,
        "key_derivation": "pbkdf2",
        "encryption_mode": "aes-256-gcm",
        "safe_logging": True,
        "receipt_storage": "local",
    }


@pytest.fixture
def export_context() -> Dict[str, Any]:
    """Standard export context for testing."""
    return {
        "route_key": "test_route_001",
        "adapter_id": "adapter_v1_20240101",
        "adapter_uri": "s3://tgf-adapters/test_route_001/adapter_v1.safetensors",
        "run_id": "run_20240101_120000",
        "training_config": {
            "learning_rate": "1e-4",
            "batch_size": "8",
            "epochs": "3",
        },
    }


@pytest.fixture
def minimal_export_context() -> Dict[str, Any]:
    """Minimal export context (route_key only)."""
    return {
        "route_key": "minimal_route",
    }
