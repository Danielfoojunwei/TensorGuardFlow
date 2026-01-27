"""
TIER 1: Contract Schema Tests

Validates exporter output schemas without requiring cloud credentials.
These tests ensure all exporters generate valid, well-formed artifacts.

Run with: pytest tests/integration/full_stack/test_contract_schemas.py -v
"""

import json
import pytest
import yaml
from typing import Dict, Any, List

from tensorguard.integrations.exporters import (
    SageMakerExporter,
    VertexAIExporter,
    AzureMLExporter,
    DatabricksExporter,
    VLLMExporter,
    TGIExporter,
    TritonExporter,
    SageMakerEndpointExporter,
)
from tensorguard.integrations.framework.contracts import ExportArtifact


class TestVLLMExporterSchema:
    """Validate vLLM exporter output schema."""

    def test_export_generates_required_files(self, vllm_exporter_config, export_context):
        """vLLM export should generate config, docker-compose, and adapter-ref."""
        exporter = VLLMExporter(vllm_exporter_config)
        artifacts = exporter.export(export_context)

        artifact_names = {a.name for a in artifacts}
        assert "vllm-config.yaml" in artifact_names
        assert "docker-compose.yaml" in artifact_names
        assert "adapter-ref.json" in artifact_names

    def test_vllm_config_schema(self, vllm_exporter_config, export_context):
        """vLLM config should have required fields."""
        exporter = VLLMExporter(vllm_exporter_config)
        artifacts = exporter.export(export_context)

        config_artifact = next(a for a in artifacts if a.name == "vllm-config.yaml")
        config = yaml.safe_load(config_artifact.content)

        # Required fields
        assert "model" in config
        assert "tensor_parallel_size" in config
        assert "max_model_len" in config
        assert "gpu_memory_utilization" in config
        assert "enable_lora" in config
        assert "tgf_integration" in config

        # TGF integration fields
        tgf = config["tgf_integration"]
        assert "route_key" in tgf
        assert "resolve_endpoint" in tgf
        assert tgf["route_key"] == export_context["route_key"]

    def test_docker_compose_schema(self, vllm_exporter_config, export_context):
        """Docker compose should be valid."""
        exporter = VLLMExporter(vllm_exporter_config)
        artifacts = exporter.export(export_context)

        compose_artifact = next(a for a in artifacts if a.name == "docker-compose.yaml")
        compose = yaml.safe_load(compose_artifact.content)

        assert "version" in compose
        assert "services" in compose
        assert "vllm" in compose["services"]
        assert "image" in compose["services"]["vllm"]
        assert "environment" in compose["services"]["vllm"]

    def test_validation_requires_route_key(self, vllm_exporter_config):
        """Export should fail without route_key."""
        exporter = VLLMExporter(vllm_exporter_config)
        with pytest.raises(ValueError, match="route_key is required"):
            exporter.export({})

    def test_validation_requires_base_model(self, export_context):
        """Export should fail without base_model in config."""
        exporter = VLLMExporter({})
        with pytest.raises(ValueError, match="base_model is required"):
            exporter.export(export_context)


class TestTGIExporterSchema:
    """Validate TGI exporter output schema."""

    def test_export_generates_required_files(self, tgi_exporter_config, export_context):
        """TGI export should generate config and docker-compose."""
        exporter = TGIExporter(tgi_exporter_config)
        artifacts = exporter.export(export_context)

        artifact_names = {a.name for a in artifacts}
        assert "tgi-config.json" in artifact_names
        assert "docker-compose.yaml" in artifact_names

    def test_tgi_config_schema(self, tgi_exporter_config, export_context):
        """TGI config should have required fields."""
        exporter = TGIExporter(tgi_exporter_config)
        artifacts = exporter.export(export_context)

        config_artifact = next(a for a in artifacts if a.name == "tgi-config.json")
        config = json.loads(config_artifact.content)

        assert "model_id" in config
        assert "max_input_length" in config
        assert "max_total_tokens" in config
        assert "tgf_integration" in config

        tgf = config["tgf_integration"]
        assert "route_key" in tgf
        assert "resolve_endpoint" in tgf


class TestTritonExporterSchema:
    """Validate Triton exporter output schema."""

    def test_export_generates_config_pbtxt(self, triton_exporter_config, export_context):
        """Triton export should generate config.pbtxt."""
        exporter = TritonExporter(triton_exporter_config)
        artifacts = exporter.export(export_context)

        artifact_names = {a.name for a in artifacts}
        assert "config.pbtxt" in artifact_names

    def test_triton_config_contains_required_sections(self, triton_exporter_config, export_context):
        """Triton config should contain required protobuf sections."""
        exporter = TritonExporter(triton_exporter_config)
        artifacts = exporter.export(export_context)

        config_artifact = next(a for a in artifacts if a.name == "config.pbtxt")
        content = config_artifact.content

        # Check required sections are present
        assert "name:" in content
        assert "platform:" in content
        assert "max_batch_size:" in content
        assert "input [" in content
        assert "output [" in content
        assert "instance_group [" in content
        assert "tgf_resolve_endpoint" in content
        assert "tgf_route_key" in content


class TestSageMakerTrainingExporterSchema:
    """Validate SageMaker training exporter output schema."""

    def test_export_generates_required_files(self, sagemaker_training_config, export_context):
        """SageMaker training export should generate job spec and scripts."""
        exporter = SageMakerExporter(sagemaker_training_config)
        artifacts = exporter.export(export_context)

        artifact_names = {a.name for a in artifacts}
        assert "sagemaker-training-job.json" in artifact_names
        assert "submit-job.sh" in artifact_names
        assert "README.md" in artifact_names

    def test_sagemaker_job_spec_schema(self, sagemaker_training_config, export_context):
        """SageMaker job spec should conform to CreateTrainingJob API schema."""
        exporter = SageMakerExporter(sagemaker_training_config)
        artifacts = exporter.export(export_context)

        job_artifact = next(a for a in artifacts if a.name == "sagemaker-training-job.json")
        job_spec = json.loads(job_artifact.content)

        # Required fields per AWS API
        assert "TrainingJobName" in job_spec
        assert "AlgorithmSpecification" in job_spec
        assert "RoleArn" in job_spec
        assert "InputDataConfig" in job_spec
        assert "OutputDataConfig" in job_spec
        assert "ResourceConfig" in job_spec
        assert "StoppingCondition" in job_spec

        # Algorithm spec
        assert "TrainingImage" in job_spec["AlgorithmSpecification"]
        assert "TrainingInputMode" in job_spec["AlgorithmSpecification"]

        # Resource config
        assert "InstanceType" in job_spec["ResourceConfig"]
        assert "InstanceCount" in job_spec["ResourceConfig"]
        assert "VolumeSizeInGB" in job_spec["ResourceConfig"]

        # TGF hyperparameters
        assert "HyperParameters" in job_spec
        assert "tgf_route_key" in job_spec["HyperParameters"]
        assert "tgf_run_id" in job_spec["HyperParameters"]

        # Tags
        assert "Tags" in job_spec
        tags_dict = {t["Key"]: t["Value"] for t in job_spec["Tags"]}
        assert tags_dict.get("tgf:managed") == "true"

    def test_job_name_length_limit(self, sagemaker_training_config, export_context):
        """SageMaker job name should not exceed 63 characters."""
        export_context["route_key"] = "a" * 100  # Very long route key
        exporter = SageMakerExporter(sagemaker_training_config)
        artifacts = exporter.export(export_context)

        job_artifact = next(a for a in artifacts if a.name == "sagemaker-training-job.json")
        job_spec = json.loads(job_artifact.content)

        assert len(job_spec["TrainingJobName"]) <= 63


class TestSageMakerEndpointExporterSchema:
    """Validate SageMaker endpoint exporter output schema."""

    def test_export_generates_required_files(self, sagemaker_endpoint_config, export_context):
        """SageMaker endpoint export should generate model, config, endpoint specs."""
        exporter = SageMakerEndpointExporter(sagemaker_endpoint_config)
        artifacts = exporter.export(export_context)

        artifact_names = {a.name for a in artifacts}
        assert "sagemaker-model.json" in artifact_names
        assert "sagemaker-endpoint-config.json" in artifact_names
        assert "sagemaker-endpoint.json" in artifact_names
        assert "deploy-endpoint.sh" in artifact_names

    def test_sagemaker_model_spec_schema(self, sagemaker_endpoint_config, export_context):
        """SageMaker model spec should conform to CreateModel API schema."""
        exporter = SageMakerEndpointExporter(sagemaker_endpoint_config)
        artifacts = exporter.export(export_context)

        model_artifact = next(a for a in artifacts if a.name == "sagemaker-model.json")
        model_spec = json.loads(model_artifact.content)

        assert "ModelName" in model_spec
        assert "PrimaryContainer" in model_spec
        assert "ExecutionRoleArn" in model_spec
        assert "Image" in model_spec["PrimaryContainer"]
        assert "Environment" in model_spec["PrimaryContainer"]

        env = model_spec["PrimaryContainer"]["Environment"]
        assert "TGF_ROUTE_KEY" in env
        assert "TGF_RESOLVE_ENDPOINT" in env

    def test_endpoint_config_spec_schema(self, sagemaker_endpoint_config, export_context):
        """SageMaker endpoint config should conform to CreateEndpointConfig API."""
        exporter = SageMakerEndpointExporter(sagemaker_endpoint_config)
        artifacts = exporter.export(export_context)

        ep_config_artifact = next(a for a in artifacts if a.name == "sagemaker-endpoint-config.json")
        ep_config = json.loads(ep_config_artifact.content)

        assert "EndpointConfigName" in ep_config
        assert "ProductionVariants" in ep_config
        assert len(ep_config["ProductionVariants"]) > 0

        variant = ep_config["ProductionVariants"][0]
        assert "VariantName" in variant
        assert "ModelName" in variant
        assert "InstanceType" in variant
        assert "InitialInstanceCount" in variant


class TestVertexAIExporterSchema:
    """Validate Vertex AI exporter output schema."""

    def test_export_generates_required_files(self, vertex_ai_config, export_context):
        """Vertex AI export should generate job spec and script."""
        exporter = VertexAIExporter(vertex_ai_config)
        artifacts = exporter.export(export_context)

        artifact_names = {a.name for a in artifacts}
        assert "vertex-custom-job.json" in artifact_names
        assert "submit-job.sh" in artifact_names

    def test_vertex_job_spec_schema(self, vertex_ai_config, export_context):
        """Vertex AI job spec should conform to CustomJob API schema."""
        exporter = VertexAIExporter(vertex_ai_config)
        artifacts = exporter.export(export_context)

        job_artifact = next(a for a in artifacts if a.name == "vertex-custom-job.json")
        job_spec = json.loads(job_artifact.content)

        assert "displayName" in job_spec
        assert "jobSpec" in job_spec
        assert "workerPoolSpecs" in job_spec["jobSpec"]

        worker_spec = job_spec["jobSpec"]["workerPoolSpecs"][0]
        assert "machineSpec" in worker_spec
        assert "containerSpec" in worker_spec

        container_spec = worker_spec["containerSpec"]
        assert "imageUri" in container_spec
        assert "env" in container_spec

        # Check TGF env vars
        env_dict = {e["name"]: e["value"] for e in container_spec["env"]}
        assert "TGF_ROUTE_KEY" in env_dict
        assert "TGF_RUN_ID" in env_dict


class TestAzureMLExporterSchema:
    """Validate Azure ML exporter output schema."""

    def test_export_generates_required_files(self, azure_ml_config, export_context):
        """Azure ML export should generate job spec and script."""
        exporter = AzureMLExporter(azure_ml_config)
        artifacts = exporter.export(export_context)

        artifact_names = {a.name for a in artifacts}
        assert "azureml-job.yaml" in artifact_names
        assert "submit-job.sh" in artifact_names

    def test_azure_job_spec_schema(self, azure_ml_config, export_context):
        """Azure ML job spec should conform to command job schema."""
        exporter = AzureMLExporter(azure_ml_config)
        artifacts = exporter.export(export_context)

        job_artifact = next(a for a in artifacts if a.name == "azureml-job.yaml")
        job_spec = yaml.safe_load(job_artifact.content)

        assert "$schema" in job_spec
        assert "type" in job_spec
        assert job_spec["type"] == "command"
        assert "display_name" in job_spec
        assert "compute" in job_spec
        assert "environment" in job_spec
        assert "command" in job_spec

        # Environment variables
        assert "environment_variables" in job_spec
        assert "TGF_ROUTE_KEY" in job_spec["environment_variables"]
        assert "TGF_RUN_ID" in job_spec["environment_variables"]


class TestDatabricksExporterSchema:
    """Validate Databricks exporter output schema."""

    def test_export_generates_required_files(self, databricks_config, export_context):
        """Databricks export should generate job spec and script."""
        exporter = DatabricksExporter(databricks_config)
        artifacts = exporter.export(export_context)

        artifact_names = {a.name for a in artifacts}
        assert "databricks-job.json" in artifact_names
        assert "submit-job.sh" in artifact_names

    def test_databricks_job_spec_schema(self, databricks_config, export_context):
        """Databricks job spec should conform to Jobs API schema."""
        exporter = DatabricksExporter(databricks_config)
        artifacts = exporter.export(export_context)

        job_artifact = next(a for a in artifacts if a.name == "databricks-job.json")
        job_spec = json.loads(job_artifact.content)

        assert "name" in job_spec
        assert "tags" in job_spec
        assert "tgf_managed" in job_spec["tags"]

        # Should have cluster config
        has_cluster = (
            "existing_cluster_id" in job_spec or
            "new_cluster" in job_spec
        )
        assert has_cluster

        # Should have task config
        has_task = (
            "notebook_task" in job_spec or
            "spark_python_task" in job_spec
        )
        assert has_task


class TestExportArtifactSchema:
    """Validate ExportArtifact dataclass structure."""

    def test_artifact_has_required_fields(self, vllm_exporter_config, export_context):
        """ExportArtifact should have name, content, and artifact_type."""
        exporter = VLLMExporter(vllm_exporter_config)
        artifacts = exporter.export(export_context)

        for artifact in artifacts:
            assert hasattr(artifact, "name")
            assert hasattr(artifact, "content")
            assert hasattr(artifact, "artifact_type")
            assert isinstance(artifact.name, str)
            assert isinstance(artifact.content, str)
            assert isinstance(artifact.artifact_type, str)

    def test_artifact_types_match_extensions(self, vllm_exporter_config, export_context):
        """Artifact type should match file extension."""
        exporter = VLLMExporter(vllm_exporter_config)
        artifacts = exporter.export(export_context)

        for artifact in artifacts:
            ext = artifact.name.split(".")[-1]
            assert artifact.artifact_type == ext


class TestMinimalContextExport:
    """Test exports with minimal context (route_key only)."""

    def test_vllm_minimal_context(self, vllm_exporter_config, minimal_export_context):
        """vLLM export should work with just route_key."""
        exporter = VLLMExporter(vllm_exporter_config)
        artifacts = exporter.export(minimal_export_context)
        assert len(artifacts) >= 1

    def test_tgi_minimal_context(self, tgi_exporter_config, minimal_export_context):
        """TGI export should work with just route_key."""
        exporter = TGIExporter(tgi_exporter_config)
        artifacts = exporter.export(minimal_export_context)
        assert len(artifacts) >= 1

    def test_triton_minimal_context(self, triton_exporter_config, minimal_export_context):
        """Triton export should work with just route_key."""
        exporter = TritonExporter(triton_exporter_config)
        artifacts = exporter.export(minimal_export_context)
        assert len(artifacts) >= 1
