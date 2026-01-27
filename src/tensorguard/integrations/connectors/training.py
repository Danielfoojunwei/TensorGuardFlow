"""
Training execution connectors (Category D).

These connectors provide training job specification export and optional execution.
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import yaml

from tensorguard.integrations.framework.contracts import (
    TrainingConnector,
    ConnectorCapability,
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.framework.manager import IntegrationRegistry


@IntegrationRegistry.register("cuda_local")
class LocalGPUConnector(TrainingConnector):
    """Connector for local GPU training execution."""

    @property
    def provider(self) -> str:
        return "cuda_local"

    @property
    def display_name(self) -> str:
        return "Local GPU (CUDA)"

    def validate_config(self) -> ValidationResult:
        """Validate local GPU configuration."""
        errors = []
        warnings = []

        device_ids = self.config.get("device_ids", [0])
        if not isinstance(device_ids, list):
            errors.append("device_ids must be a list")

        memory_fraction = self.config.get("memory_fraction", 0.9)
        if not 0.1 <= memory_fraction <= 1.0:
            errors.append("memory_fraction must be between 0.1 and 1.0")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check CUDA availability."""
        start_time = time.time()

        try:
            import torch

            cuda_available = torch.cuda.is_available()
            if not cuda_available:
                return HealthCheckResult(
                    status="FAIL",
                    message="CUDA not available",
                    latency_ms=int((time.time() - start_time) * 1000),
                )

            device_count = torch.cuda.device_count()
            device_ids = self.config.get("device_ids", [0])

            # Verify requested devices exist
            for device_id in device_ids:
                if device_id >= device_count:
                    return HealthCheckResult(
                        status="FAIL",
                        message=f"Device {device_id} not found (only {device_count} devices)",
                        latency_ms=int((time.time() - start_time) * 1000),
                    )

            devices_info = []
            for i in range(device_count):
                props = torch.cuda.get_device_properties(i)
                devices_info.append({
                    "id": i,
                    "name": props.name,
                    "memory_gb": props.total_memory / 1e9,
                })

            return HealthCheckResult(
                status="OK",
                message=f"{device_count} GPU(s) available",
                latency_ms=int((time.time() - start_time) * 1000),
                details={
                    "cuda_version": torch.version.cuda,
                    "device_count": device_count,
                    "devices": devices_info,
                },
            )

        except ImportError:
            return HealthCheckResult(
                status="WARN",
                message="PyTorch not installed - cannot verify CUDA",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        except Exception as e:
            return HealthCheckResult(
                status="FAIL",
                message=f"CUDA check failed: {str(e)}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.LOCAL_TRAINING,
            ConnectorCapability.MIXED_PRECISION,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test on local GPU."""
        start_time = time.time()

        try:
            import torch

            if not torch.cuda.is_available():
                return SmokeTestResult(
                    passed=False,
                    test_name="cuda_check",
                    duration_ms=int((time.time() - start_time) * 1000),
                    message="CUDA not available",
                )

            # Try simple tensor operation
            device = torch.device("cuda:0")
            x = torch.randn(10, 10, device=device)
            y = x @ x.T
            del x, y
            torch.cuda.empty_cache()

            return SmokeTestResult(
                passed=True,
                test_name="cuda_tensor_op",
                duration_ms=int((time.time() - start_time) * 1000),
                message="CUDA tensor operations working",
            )

        except ImportError:
            return SmokeTestResult(
                passed=True,
                test_name="cuda_check",
                duration_ms=int((time.time() - start_time) * 1000),
                message="PyTorch not installed - skipped",
                details={"validation_only": True},
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="cuda_tensor_op",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def export_job_spec(
        self,
        context: Dict[str, Any],
    ) -> ExportArtifact:
        """Export local training configuration."""
        device_ids = self.config.get("device_ids", [0])
        mixed_precision = self.config.get("mixed_precision", True)
        memory_fraction = self.config.get("memory_fraction", 0.9)

        config_content = yaml.dump({
            "provider": "cuda_local",
            "route_key": context.get("route_key", "unknown"),
            "run_id": context.get("run_id", "unknown"),
            "device_ids": device_ids,
            "mixed_precision": mixed_precision,
            "memory_fraction": memory_fraction,
            "timestamp": datetime.utcnow().isoformat(),
        }, default_flow_style=False)

        return ExportArtifact(
            name="local-training-config.yaml",
            content=config_content,
            artifact_type="yaml",
        )

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export training artifacts."""
        return [await self.export_job_spec(context)]

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        return []  # Local execution, no endpoints


@IntegrationRegistry.register("kubernetes")
class KubernetesConnector(TrainingConnector):
    """Connector for Kubernetes training jobs."""

    @property
    def provider(self) -> str:
        return "kubernetes"

    @property
    def display_name(self) -> str:
        return "Kubernetes"

    def validate_config(self) -> ValidationResult:
        """Validate Kubernetes configuration."""
        errors = []
        warnings = []

        image = self.config.get("image")
        if not image:
            errors.append("image is required")

        namespace = self.config.get("namespace", "default")
        if namespace == "default":
            warnings.append("Using 'default' namespace - consider a dedicated namespace")

        gpu_count = self.config.get("gpu_count", 1)
        if gpu_count < 0:
            errors.append("gpu_count must be non-negative")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check Kubernetes cluster accessibility."""
        start_time = time.time()

        try:
            from kubernetes import client, config as k8s_config

            # Try to load config
            try:
                k8s_config.load_incluster_config()
            except k8s_config.ConfigException:
                k8s_config.load_kube_config()

            v1 = client.CoreV1Api()
            namespace = self.config.get("namespace", "default")

            # Try to list pods in namespace
            pods = v1.list_namespaced_pod(namespace=namespace, limit=1)

            return HealthCheckResult(
                status="OK",
                message=f"Cluster accessible, namespace '{namespace}' exists",
                latency_ms=int((time.time() - start_time) * 1000),
                details={"namespace": namespace},
            )

        except ImportError:
            return HealthCheckResult(
                status="WARN",
                message="kubernetes client not installed - schema validation only",
                latency_ms=int((time.time() - start_time) * 1000),
                details={"validation_only": True},
            )

        except Exception as e:
            return HealthCheckResult(
                status="FAIL",
                message=f"Kubernetes access failed: {str(e)}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.JOB_EXPORT,
            ConnectorCapability.GPU_SCHEDULING,
            ConnectorCapability.REMOTE_TRAINING,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test by validating job spec generation."""
        start_time = time.time()

        try:
            # Generate a test job spec
            context = {
                "route_key": "smoke-test",
                "run_id": "smoke-test-001",
            }
            artifact = await self.export_job_spec(context)

            # Validate YAML is parseable
            parsed = yaml.safe_load(artifact.content)
            if parsed.get("kind") != "Job":
                raise ValueError("Invalid Job kind")

            return SmokeTestResult(
                passed=True,
                test_name="job_spec_generation",
                duration_ms=int((time.time() - start_time) * 1000),
                message="Job spec generation successful",
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="job_spec_generation",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def export_job_spec(
        self,
        context: Dict[str, Any],
    ) -> ExportArtifact:
        """Export Kubernetes Job YAML."""
        namespace = self.config.get("namespace", "default")
        image = self.config.get("image", "training:latest")
        gpu_count = self.config.get("gpu_count", 1)
        cpu_request = self.config.get("cpu_request", "4")
        memory_request = self.config.get("memory_request", "16Gi")
        data_pvc = self.config.get("data_pvc")
        output_pvc = self.config.get("output_pvc")
        service_account = self.config.get("service_account")
        node_selector = self.config.get("node_selector", {})
        tolerations = self.config.get("tolerations", [])
        image_pull_secrets = self.config.get("image_pull_secrets", [])

        route_key = context.get("route_key", "unknown")
        run_id = context.get("run_id", "unknown")
        job_name = f"tgf-training-{route_key}-{run_id}"[:63]  # K8s name limit

        job_spec = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "tensorguardflow",
                    "tgf.io/route-key": route_key,
                    "tgf.io/run-id": run_id,
                },
            },
            "spec": {
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/managed-by": "tensorguardflow",
                            "tgf.io/route-key": route_key,
                        },
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "trainer",
                                "image": image,
                                "env": [
                                    {"name": "TGF_RUN_ID", "value": run_id},
                                    {"name": "TGF_ROUTE_KEY", "value": route_key},
                                ],
                                "resources": {
                                    "requests": {
                                        "cpu": cpu_request,
                                        "memory": memory_request,
                                    },
                                    "limits": {},
                                },
                                "volumeMounts": [],
                            }
                        ],
                        "volumes": [],
                        "restartPolicy": "Never",
                    },
                },
                "backoffLimit": 3,
            },
        }

        # Add GPU resources
        if gpu_count > 0:
            job_spec["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["nvidia.com/gpu"] = gpu_count

        # Add data PVC if specified
        if data_pvc:
            job_spec["spec"]["template"]["spec"]["volumes"].append({
                "name": "data",
                "persistentVolumeClaim": {"claimName": data_pvc},
            })
            job_spec["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append({
                "name": "data",
                "mountPath": "/data",
            })

        # Add output PVC if specified
        if output_pvc:
            job_spec["spec"]["template"]["spec"]["volumes"].append({
                "name": "output",
                "persistentVolumeClaim": {"claimName": output_pvc},
            })
            job_spec["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append({
                "name": "output",
                "mountPath": "/output",
            })

        # Add service account if specified
        if service_account:
            job_spec["spec"]["template"]["spec"]["serviceAccountName"] = service_account

        # Add node selector if specified
        if node_selector:
            job_spec["spec"]["template"]["spec"]["nodeSelector"] = node_selector

        # Add tolerations if specified
        if tolerations:
            job_spec["spec"]["template"]["spec"]["tolerations"] = tolerations

        # Add image pull secrets if specified
        if image_pull_secrets:
            job_spec["spec"]["template"]["spec"]["imagePullSecrets"] = [
                {"name": secret} for secret in image_pull_secrets
            ]

        return ExportArtifact(
            name="training-job.yaml",
            content=yaml.dump(job_spec, default_flow_style=False),
            artifact_type="yaml",
            metadata={
                "namespace": namespace,
                "job_name": job_name,
            },
        )

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export all Kubernetes training artifacts."""
        artifacts = []

        # Main job spec
        artifacts.append(await self.export_job_spec(context))

        # ConfigMap for training config
        route_key = context.get("route_key", "unknown")
        run_id = context.get("run_id", "unknown")
        training_config = context.get("training_config", {})

        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"tgf-config-{route_key}-{run_id}"[:63],
                "namespace": self.config.get("namespace", "default"),
                "labels": {
                    "app.kubernetes.io/managed-by": "tensorguardflow",
                    "tgf.io/route-key": route_key,
                },
            },
            "data": {
                "training-config.json": json.dumps(training_config, indent=2),
            },
        }

        artifacts.append(
            ExportArtifact(
                name="configmap.yaml",
                content=yaml.dump(configmap, default_flow_style=False),
                artifact_type="yaml",
            )
        )

        return artifacts

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        return [
            {
                "endpoint": "kubernetes.default.svc",
                "type": "outbound",
                "protocol": "https",
                "auth_method": "mtls",
            }
        ]
