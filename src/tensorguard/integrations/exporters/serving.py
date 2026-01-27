"""
Serving platform exporters.

These exporters generate serving configuration packs for inference platforms.
"""

import json
from datetime import datetime
from typing import Any, Dict, List
import yaml

from tensorguard.integrations.framework.contracts import ExportArtifact


class VLLMExporter:
    """Exporter for vLLM serving configurations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def validate_context(self, context: Dict[str, Any]) -> List[str]:
        """Validate export context."""
        errors = []
        if not context.get("route_key"):
            errors.append("route_key is required")
        if not self.config.get("base_model"):
            errors.append("base_model is required in config")
        return errors

    def export(self, context: Dict[str, Any]) -> List[ExportArtifact]:
        """Export vLLM serving pack."""
        errors = self.validate_context(context)
        if errors:
            raise ValueError(f"Invalid context: {errors}")

        route_key = context["route_key"]
        adapter_id = context.get("adapter_id", "unknown")
        adapter_uri = context.get("adapter_uri", "")
        resolve_endpoint = self.config.get("resolve_endpoint", "/tgflow/resolve")

        base_model = self.config["base_model"]
        tensor_parallel_size = self.config.get("tensor_parallel_size", 1)
        max_model_len = self.config.get("max_model_len", 4096)
        gpu_memory_utilization = self.config.get("gpu_memory_utilization", 0.9)

        # Main config
        vllm_config = {
            "model": base_model,
            "tensor_parallel_size": tensor_parallel_size,
            "max_model_len": max_model_len,
            "gpu_memory_utilization": gpu_memory_utilization,
            "enable_lora": True,
            "lora_modules": [
                {
                    "name": route_key,
                    "path": adapter_uri,
                }
            ] if adapter_uri else [],
            "tgf_integration": {
                "route_key": route_key,
                "resolve_endpoint": resolve_endpoint,
                "adapter_id": adapter_id,
            },
        }

        artifacts = [
            ExportArtifact(
                name="vllm-config.yaml",
                content=yaml.dump(vllm_config, default_flow_style=False),
                artifact_type="yaml",
            )
        ]

        # Docker compose
        compose = {
            "version": "3.8",
            "services": {
                "vllm": {
                    "image": "vllm/vllm-openai:latest",
                    "runtime": "nvidia",
                    "environment": {
                        "NVIDIA_VISIBLE_DEVICES": "all",
                        "TGF_RESOLVE_ENDPOINT": resolve_endpoint,
                        "TGF_ROUTE_KEY": route_key,
                    },
                    "ports": ["8000:8000"],
                    "volumes": [
                        "./vllm-config.yaml:/config/vllm-config.yaml:ro",
                        "./adapters:/adapters:ro",
                    ],
                    "command": f"--model {base_model} --tensor-parallel-size {tensor_parallel_size} --max-model-len {max_model_len}",
                }
            },
        }

        artifacts.append(
            ExportArtifact(
                name="docker-compose.yaml",
                content=yaml.dump(compose, default_flow_style=False),
                artifact_type="yaml",
            )
        )

        # Adapter reference
        artifacts.append(
            ExportArtifact(
                name="adapter-ref.json",
                content=json.dumps({
                    "adapter_id": adapter_id,
                    "adapter_uri": adapter_uri,
                    "route_key": route_key,
                    "generated_at": datetime.utcnow().isoformat(),
                }, indent=2),
                artifact_type="json",
            )
        )

        return artifacts


class TGIExporter:
    """Exporter for Text Generation Inference configurations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def validate_context(self, context: Dict[str, Any]) -> List[str]:
        """Validate export context."""
        errors = []
        if not context.get("route_key"):
            errors.append("route_key is required")
        if not self.config.get("base_model"):
            errors.append("base_model is required in config")
        return errors

    def export(self, context: Dict[str, Any]) -> List[ExportArtifact]:
        """Export TGI serving pack."""
        errors = self.validate_context(context)
        if errors:
            raise ValueError(f"Invalid context: {errors}")

        route_key = context["route_key"]
        adapter_uri = context.get("adapter_uri", "")
        resolve_endpoint = self.config.get("resolve_endpoint", "/tgflow/resolve")

        base_model = self.config["base_model"]

        tgi_config = {
            "model_id": base_model,
            "max_input_length": self.config.get("max_input_length", 1024),
            "max_total_tokens": self.config.get("max_total_tokens", 2048),
            "quantize": self.config.get("quantize"),
            "lora_adapters": adapter_uri if adapter_uri else None,
            "tgf_integration": {
                "route_key": route_key,
                "resolve_endpoint": resolve_endpoint,
            },
        }

        artifacts = [
            ExportArtifact(
                name="tgi-config.json",
                content=json.dumps(tgi_config, indent=2),
                artifact_type="json",
            )
        ]

        # Docker compose
        compose = {
            "version": "3.8",
            "services": {
                "tgi": {
                    "image": "ghcr.io/huggingface/text-generation-inference:latest",
                    "runtime": "nvidia",
                    "environment": {
                        "NVIDIA_VISIBLE_DEVICES": "all",
                        "TGF_RESOLVE_ENDPOINT": resolve_endpoint,
                        "TGF_ROUTE_KEY": route_key,
                    },
                    "ports": ["8080:80"],
                    "volumes": ["./adapters:/adapters:ro"],
                    "command": f"--model-id {base_model}",
                }
            },
        }

        artifacts.append(
            ExportArtifact(
                name="docker-compose.yaml",
                content=yaml.dump(compose, default_flow_style=False),
                artifact_type="yaml",
            )
        )

        return artifacts


class TritonExporter:
    """Exporter for NVIDIA Triton configurations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def validate_context(self, context: Dict[str, Any]) -> List[str]:
        """Validate export context."""
        errors = []
        if not context.get("route_key"):
            errors.append("route_key is required")
        if not self.config.get("model_name"):
            errors.append("model_name is required in config")
        return errors

    def export(self, context: Dict[str, Any]) -> List[ExportArtifact]:
        """Export Triton serving pack."""
        errors = self.validate_context(context)
        if errors:
            raise ValueError(f"Invalid context: {errors}")

        route_key = context["route_key"]
        resolve_endpoint = self.config.get("resolve_endpoint", "/tgflow/resolve")

        model_name = self.config["model_name"]
        max_batch_size = self.config.get("max_batch_size", 8)
        instance_count = self.config.get("instance_count", 1)

        config_pbtxt = f'''name: "{model_name}"
platform: "pytorch_libtorch"
max_batch_size: {max_batch_size}

input [
  {{
    name: "input_ids"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }},
  {{
    name: "attention_mask"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }}
]

output [
  {{
    name: "logits"
    data_type: TYPE_FP32
    dims: [ -1, -1 ]
  }}
]

instance_group [
  {{
    count: {instance_count}
    kind: KIND_GPU
  }}
]

parameters: {{
  key: "tgf_resolve_endpoint"
  value: {{ string_value: "{resolve_endpoint}" }}
}}

parameters: {{
  key: "tgf_route_key"
  value: {{ string_value: "{route_key}" }}
}}
'''

        artifacts = [
            ExportArtifact(
                name="config.pbtxt",
                content=config_pbtxt,
                artifact_type="pbtxt",
            )
        ]

        return artifacts


class SageMakerEndpointExporter:
    """Exporter for SageMaker endpoint configurations (template only)."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def validate_context(self, context: Dict[str, Any]) -> List[str]:
        """Validate export context."""
        errors = []
        if not context.get("route_key"):
            errors.append("route_key is required")
        if not self.config.get("role_arn"):
            errors.append("role_arn is required in config")
        if not self.config.get("inference_image"):
            errors.append("inference_image is required in config")
        return errors

    def export(self, context: Dict[str, Any]) -> List[ExportArtifact]:
        """Export SageMaker endpoint specification."""
        errors = self.validate_context(context)
        if errors:
            raise ValueError(f"Invalid context: {errors}")

        route_key = context["route_key"]
        adapter_uri = context.get("adapter_uri", "")
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        model_name = f"tgf-{route_key}-{timestamp}"[:63]
        endpoint_config_name = f"tgf-ep-cfg-{route_key}-{timestamp}"[:63]
        endpoint_name = f"tgf-ep-{route_key}"[:63]

        # Model definition
        model_spec = {
            "ModelName": model_name,
            "PrimaryContainer": {
                "Image": self.config["inference_image"],
                "ModelDataUrl": adapter_uri or self.config.get("model_data_url", ""),
                "Environment": {
                    "TGF_ROUTE_KEY": route_key,
                    "TGF_RESOLVE_ENDPOINT": self.config.get("resolve_endpoint", "/tgflow/resolve"),
                },
            },
            "ExecutionRoleArn": self.config["role_arn"],
            "Tags": [
                {"Key": "tgf:managed", "Value": "true"},
                {"Key": "tgf:route-key", "Value": route_key},
            ],
        }

        # Endpoint config
        endpoint_config_spec = {
            "EndpointConfigName": endpoint_config_name,
            "ProductionVariants": [
                {
                    "VariantName": "primary",
                    "ModelName": model_name,
                    "InstanceType": self.config.get("instance_type", "ml.g5.xlarge"),
                    "InitialInstanceCount": self.config.get("initial_instance_count", 1),
                }
            ],
            "Tags": [
                {"Key": "tgf:managed", "Value": "true"},
                {"Key": "tgf:route-key", "Value": route_key},
            ],
        }

        # Endpoint
        endpoint_spec = {
            "EndpointName": endpoint_name,
            "EndpointConfigName": endpoint_config_name,
            "Tags": [
                {"Key": "tgf:managed", "Value": "true"},
                {"Key": "tgf:route-key", "Value": route_key},
            ],
        }

        artifacts = [
            ExportArtifact(
                name="sagemaker-model.json",
                content=json.dumps(model_spec, indent=2),
                artifact_type="json",
            ),
            ExportArtifact(
                name="sagemaker-endpoint-config.json",
                content=json.dumps(endpoint_config_spec, indent=2),
                artifact_type="json",
            ),
            ExportArtifact(
                name="sagemaker-endpoint.json",
                content=json.dumps(endpoint_spec, indent=2),
                artifact_type="json",
            ),
        ]

        # Deployment script
        deploy_script = f'''#!/bin/bash
# SageMaker Endpoint Deployment Script
# Generated by TensorGuardFlow

set -e

echo "Creating model..."
aws sagemaker create-model --cli-input-json file://sagemaker-model.json

echo "Creating endpoint configuration..."
aws sagemaker create-endpoint-config --cli-input-json file://sagemaker-endpoint-config.json

echo "Creating endpoint..."
aws sagemaker create-endpoint --cli-input-json file://sagemaker-endpoint.json

echo "Endpoint creation initiated: {endpoint_name}"
echo "Monitor with: aws sagemaker describe-endpoint --endpoint-name {endpoint_name}"
'''

        artifacts.append(
            ExportArtifact(
                name="deploy-endpoint.sh",
                content=deploy_script,
                artifact_type="sh",
            )
        )

        return artifacts
