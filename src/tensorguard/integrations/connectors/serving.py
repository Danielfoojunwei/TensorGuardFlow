"""
Serving/inference connectors (Category F).

These connectors provide serving pack export and /resolve integration.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List
import yaml

from tensorguard.integrations.framework.contracts import (
    ServingConnector,
    ConnectorCapability,
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.framework.manager import IntegrationRegistry


@IntegrationRegistry.register("vllm")
class VLLMConnector(ServingConnector):
    """Connector for vLLM serving."""

    @property
    def provider(self) -> str:
        return "vllm"

    @property
    def display_name(self) -> str:
        return "vLLM"

    def validate_config(self) -> ValidationResult:
        """Validate vLLM configuration."""
        errors = []
        warnings = []

        base_model = self.config.get("base_model")
        if not base_model:
            errors.append("base_model is required")

        tensor_parallel_size = self.config.get("tensor_parallel_size", 1)
        if tensor_parallel_size < 1:
            errors.append("tensor_parallel_size must be >= 1")

        gpu_memory_utilization = self.config.get("gpu_memory_utilization", 0.9)
        if not 0.1 <= gpu_memory_utilization <= 1.0:
            errors.append("gpu_memory_utilization must be between 0.1 and 1.0")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check vLLM configuration validity."""
        start_time = time.time()

        # vLLM is export-only, so we just validate config
        validation = self.validate_config()

        if not validation.valid:
            return HealthCheckResult(
                status="FAIL",
                message=f"Configuration invalid: {validation.errors}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        return HealthCheckResult(
            status="OK",
            message="vLLM configuration valid (export-only)",
            latency_ms=int((time.time() - start_time) * 1000),
            details={"base_model": self.config.get("base_model")},
        )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.SERVING_PACK_EXPORT,
            ConnectorCapability.RESOLVE_INTEGRATION,
            ConnectorCapability.LORA_LOADING,
            ConnectorCapability.DYNAMIC_ADAPTER,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test by generating serving pack."""
        start_time = time.time()

        try:
            context = {
                "route_key": "smoke-test",
                "adapter_id": "adpt_test123",
                "adapter_uri": "s3://adapters/test/",
            }
            artifacts = await self.export_serving_pack(context)

            if not artifacts:
                raise ValueError("No artifacts generated")

            # Validate YAML
            config_artifact = next(
                (a for a in artifacts if a.name == "vllm-config.yaml"),
                None
            )
            if config_artifact:
                yaml.safe_load(config_artifact.content)

            return SmokeTestResult(
                passed=True,
                test_name="serving_pack_generation",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Generated {len(artifacts)} artifacts",
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="serving_pack_generation",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def export_serving_pack(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export vLLM serving configuration pack."""
        base_model = self.config.get("base_model", "unknown")
        tensor_parallel_size = self.config.get("tensor_parallel_size", 1)
        max_model_len = self.config.get("max_model_len", 4096)
        gpu_memory_utilization = self.config.get("gpu_memory_utilization", 0.9)

        route_key = context.get("route_key", "unknown")
        adapter_id = context.get("adapter_id", "unknown")
        adapter_uri = context.get("adapter_uri", "")
        resolve_endpoint = self.config.get("resolve_endpoint", "/tgflow/resolve")

        artifacts = []

        # Main vLLM config
        vllm_config = {
            "model": base_model,
            "tensor_parallel_size": tensor_parallel_size,
            "max_model_len": max_model_len,
            "gpu_memory_utilization": gpu_memory_utilization,
            "lora_modules": [
                {
                    "name": route_key,
                    "path": adapter_uri,
                    "tgf_adapter_id": adapter_id,
                    "tgf_resolve_endpoint": resolve_endpoint,
                }
            ],
            "tgf_integration": {
                "route_key": route_key,
                "resolve_endpoint": resolve_endpoint,
                "auto_refresh": True,
                "refresh_interval_seconds": 60,
            },
        }

        artifacts.append(
            ExportArtifact(
                name="vllm-config.yaml",
                content=yaml.dump(vllm_config, default_flow_style=False),
                artifact_type="yaml",
                metadata={"base_model": base_model},
            )
        )

        # Adapter reference
        adapter_ref = {
            "adapter_id": adapter_id,
            "adapter_uri": adapter_uri,
            "route_key": route_key,
            "timestamp": datetime.utcnow().isoformat(),
        }

        artifacts.append(
            ExportArtifact(
                name="adapter-ref.json",
                content=json.dumps(adapter_ref, indent=2),
                artifact_type="json",
            )
        )

        # Docker compose for local testing
        compose_content = f"""version: '3.8'

services:
  vllm:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - TGF_RESOLVE_ENDPOINT={resolve_endpoint}
      - TGF_ROUTE_KEY={route_key}
    volumes:
      - ./vllm-config.yaml:/config/vllm-config.yaml:ro
      - ./adapters:/adapters:ro
    ports:
      - "8000:8000"
    command: >
      --model {base_model}
      --tensor-parallel-size {tensor_parallel_size}
      --max-model-len {max_model_len}
      --gpu-memory-utilization {gpu_memory_utilization}
"""

        artifacts.append(
            ExportArtifact(
                name="docker-compose.yaml",
                content=compose_content,
                artifact_type="yaml",
            )
        )

        # Resolve integration code
        artifacts.append(
            ExportArtifact(
                name="resolve-integration.py",
                content=self.get_resolve_integration_code(),
                artifact_type="py",
            )
        )

        # README
        readme_content = f"""# vLLM Serving Pack for {route_key}

## Generated
{datetime.utcnow().isoformat()}

## Base Model
{base_model}

## Files
- `vllm-config.yaml` - vLLM server configuration
- `adapter-ref.json` - Current adapter reference
- `docker-compose.yaml` - Docker Compose for local testing
- `resolve-integration.py` - TGF /resolve integration code

## Usage

### Local Testing
```bash
docker-compose up
```

### Production
1. Deploy vLLM with your orchestration tool
2. Mount adapter storage
3. Configure TGF_RESOLVE_ENDPOINT environment variable
4. Use resolve-integration.py for adapter refresh

## TGF /resolve Integration

The runtime should call `/tgflow/resolve` to get the current adapter:

```python
from resolve_integration import TGFResolver

resolver = TGFResolver("{resolve_endpoint}", api_key="YOUR_KEY")
adapter = await resolver.resolve("{route_key}")
```
"""

        artifacts.append(
            ExportArtifact(
                name="README.md",
                content=readme_content,
                artifact_type="md",
            )
        )

        return artifacts

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export all vLLM artifacts."""
        return await self.export_serving_pack(context)

    def get_resolve_integration_code(self) -> str:
        """Return Python code for /resolve integration."""
        return '''"""
TGF Resolve Integration for vLLM
"""
import asyncio
import httpx
import os
from typing import Optional


class TGFResolver:
    """Client for TGF /resolve endpoint."""

    def __init__(self, tgf_url: str, api_key: Optional[str] = None):
        self.tgf_url = tgf_url.rstrip('/')
        self.api_key = api_key or os.environ.get("TGF_API_KEY", "")
        self._cache = {}
        self._cache_ttl = 60  # seconds

    async def resolve(
        self,
        route_key: str,
        channel: str = "stable",
        request_context: Optional[dict] = None
    ) -> dict:
        """Resolve current adapter for route."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.tgf_url}/tgflow/resolve",
                json={
                    "route_key": route_key,
                    "channel": channel,
                    "request_context": request_context or {}
                },
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()

    async def resolve_cached(
        self,
        route_key: str,
        channel: str = "stable"
    ) -> dict:
        """Resolve with caching."""
        import time

        cache_key = f"{route_key}:{channel}"
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if (time.time() - entry['time']) < self._cache_ttl:
                return entry['data']

        result = await self.resolve(route_key, channel)
        self._cache[cache_key] = {
            'data': result,
            'time': time.time()
        }
        return result

    def set_cache_ttl(self, ttl_seconds: int) -> None:
        """Set cache TTL in seconds."""
        self._cache_ttl = ttl_seconds

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        self._cache.clear()


# Example usage
if __name__ == "__main__":
    async def main():
        resolver = TGFResolver(
            tgf_url=os.environ.get("TGF_URL", "http://localhost:8080"),
            api_key=os.environ.get("TGF_API_KEY")
        )

        route_key = os.environ.get("TGF_ROUTE_KEY", "default")
        result = await resolver.resolve(route_key)

        print(f"Adapter ID: {result.get('adapter_id')}")
        print(f"Adapter URI: {result.get('adapter_uri')}")
        print(f"Signature Status: {result.get('signature_status')}")

    asyncio.run(main())
'''

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        resolve_endpoint = self.config.get("resolve_endpoint", "/tgflow/resolve")
        return [
            {
                "endpoint": resolve_endpoint,
                "type": "inbound",
                "protocol": "https",
                "auth_method": "api_key",
            }
        ]


@IntegrationRegistry.register("tgi")
class TGIConnector(ServingConnector):
    """Connector for Text Generation Inference (TGI)."""

    @property
    def provider(self) -> str:
        return "tgi"

    @property
    def display_name(self) -> str:
        return "Text Generation Inference (TGI)"

    def validate_config(self) -> ValidationResult:
        """Validate TGI configuration."""
        errors = []

        base_model = self.config.get("base_model")
        if not base_model:
            errors.append("base_model is required")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check TGI configuration validity."""
        start_time = time.time()

        validation = self.validate_config()
        if not validation.valid:
            return HealthCheckResult(
                status="FAIL",
                message=f"Configuration invalid: {validation.errors}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        return HealthCheckResult(
            status="OK",
            message="TGI configuration valid (export-only)",
            latency_ms=int((time.time() - start_time) * 1000),
        )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.SERVING_PACK_EXPORT,
            ConnectorCapability.RESOLVE_INTEGRATION,
            ConnectorCapability.LORA_LOADING,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Smoke test TGI configuration."""
        start_time = time.time()

        try:
            context = {"route_key": "smoke-test"}
            artifacts = await self.export_serving_pack(context)

            return SmokeTestResult(
                passed=True,
                test_name="serving_pack_generation",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Generated {len(artifacts)} artifacts",
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="serving_pack_generation",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def export_serving_pack(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export TGI serving pack."""
        base_model = self.config.get("base_model", "unknown")
        max_input_length = self.config.get("max_input_length", 1024)
        max_total_tokens = self.config.get("max_total_tokens", 2048)

        route_key = context.get("route_key", "unknown")
        adapter_uri = context.get("adapter_uri", "")
        resolve_endpoint = self.config.get("resolve_endpoint", "/tgflow/resolve")

        tgi_config = {
            "model_id": base_model,
            "max_input_length": max_input_length,
            "max_total_tokens": max_total_tokens,
            "lora_adapters": adapter_uri,
            "tgf_integration": {
                "resolve_endpoint": resolve_endpoint,
                "route_key": route_key,
            },
        }

        return [
            ExportArtifact(
                name="tgi-config.json",
                content=json.dumps(tgi_config, indent=2),
                artifact_type="json",
            )
        ]

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        return await self.export_serving_pack(context)

    def get_resolve_integration_code(self) -> str:
        return "# TGI uses the same resolve integration as vLLM"

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        return [
            {
                "endpoint": self.config.get("resolve_endpoint", "/tgflow/resolve"),
                "type": "inbound",
                "protocol": "https",
            }
        ]


@IntegrationRegistry.register("triton")
class TritonConnector(ServingConnector):
    """Connector for NVIDIA Triton Inference Server."""

    @property
    def provider(self) -> str:
        return "triton"

    @property
    def display_name(self) -> str:
        return "NVIDIA Triton"

    def validate_config(self) -> ValidationResult:
        """Validate Triton configuration."""
        errors = []

        model_name = self.config.get("model_name")
        if not model_name:
            errors.append("model_name is required")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check Triton configuration validity."""
        start_time = time.time()

        validation = self.validate_config()
        if not validation.valid:
            return HealthCheckResult(
                status="FAIL",
                message=f"Configuration invalid: {validation.errors}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        return HealthCheckResult(
            status="OK",
            message="Triton configuration valid (export-only)",
            latency_ms=int((time.time() - start_time) * 1000),
        )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.SERVING_PACK_EXPORT,
            ConnectorCapability.RESOLVE_INTEGRATION,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Smoke test Triton configuration."""
        start_time = time.time()

        try:
            context = {"route_key": "smoke-test"}
            artifacts = await self.export_serving_pack(context)

            return SmokeTestResult(
                passed=True,
                test_name="serving_pack_generation",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Generated {len(artifacts)} artifacts",
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="serving_pack_generation",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def export_serving_pack(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export Triton model configuration."""
        model_name = self.config.get("model_name", "model")
        max_batch_size = self.config.get("max_batch_size", 8)
        instance_count = self.config.get("instance_count", 1)

        route_key = context.get("route_key", "unknown")
        resolve_endpoint = self.config.get("resolve_endpoint", "/tgflow/resolve")

        # Triton config.pbtxt format
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

        return [
            ExportArtifact(
                name="config.pbtxt",
                content=config_pbtxt,
                artifact_type="pbtxt",
                metadata={"model_name": model_name},
            )
        ]

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        return await self.export_serving_pack(context)

    def get_resolve_integration_code(self) -> str:
        return "# Triton uses model config parameters for TGF integration"

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        return [
            {
                "endpoint": self.config.get("resolve_endpoint", "/tgflow/resolve"),
                "type": "inbound",
                "protocol": "https",
            }
        ]
