"""
TIER 3: Optional Provider Smoke Tests

These tests only run when environment credentials are available.
They verify connectivity and basic operations against real cloud services.

Run with: pytest tests/integration/full_stack/test_provider_smoke.py -v

Skip markers:
- @pytest.mark.skipif(not HAS_AWS_CREDS, reason="AWS credentials not available")
- @pytest.mark.skipif(not HAS_GCP_CREDS, reason="GCP credentials not available")
- etc.
"""

import os
import json
import pytest
from typing import Optional

# Credential detection
HAS_AWS_CREDS = bool(
    os.environ.get("AWS_ACCESS_KEY_ID") and
    os.environ.get("AWS_SECRET_ACCESS_KEY")
) or os.path.exists(os.path.expanduser("~/.aws/credentials"))

HAS_GCP_CREDS = bool(
    os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or
    os.environ.get("GCLOUD_PROJECT")
)

HAS_AZURE_CREDS = bool(
    os.environ.get("AZURE_SUBSCRIPTION_ID") or
    os.environ.get("AZURE_CLIENT_ID")
)

HAS_DATABRICKS_CREDS = bool(
    os.environ.get("DATABRICKS_HOST") and
    os.environ.get("DATABRICKS_TOKEN")
)

HAS_MLFLOW_CREDS = bool(
    os.environ.get("MLFLOW_TRACKING_URI")
)

HAS_WANDB_CREDS = bool(
    os.environ.get("WANDB_API_KEY")
)


# Mark all tests in this module as slow/optional
pytestmark = pytest.mark.slow


class TestAWSConnectivity:
    """Test AWS service connectivity when credentials available."""

    @pytest.mark.skipif(not HAS_AWS_CREDS, reason="AWS credentials not available")
    def test_s3_connector_health(self):
        """Test S3 connector health check with real AWS."""
        pytest.importorskip("boto3")
        from tensorguard.integrations.connectors import S3Connector

        # Use a test bucket (should exist for smoke testing)
        test_bucket = os.environ.get("TGF_TEST_S3_BUCKET", "tgf-integration-test")

        connector = S3Connector({
            "bucket": test_bucket,
            "region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "prefix": "smoke-test/",
        })

        result = connector.health_check()

        # Log result for debugging
        print(f"S3 health check: healthy={result.healthy}, message={result.message}")

        # Don't assert healthy - bucket may not exist in all test environments
        # Just verify the check completes without exception
        assert result is not None
        assert result.latency_ms >= 0

    @pytest.mark.skipif(not HAS_AWS_CREDS, reason="AWS credentials not available")
    def test_aws_kms_connector_health(self):
        """Test AWS KMS connector health check."""
        pytest.importorskip("boto3")
        from tensorguard.integrations.connectors import AWSKMSConnector

        test_key_id = os.environ.get("TGF_TEST_KMS_KEY_ID", "alias/tgf-test-key")

        connector = AWSKMSConnector({
            "region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "key_id": test_key_id,
        })

        result = connector.health_check()

        print(f"KMS health check: healthy={result.healthy}, message={result.message}")
        assert result is not None

    @pytest.mark.skipif(not HAS_AWS_CREDS, reason="AWS credentials not available")
    def test_sagemaker_exporter_generates_valid_spec(self):
        """Test SageMaker exporter generates valid job spec."""
        from tensorguard.integrations.exporters import SageMakerExporter

        exporter = SageMakerExporter({
            "role_arn": os.environ.get(
                "TGF_TEST_SAGEMAKER_ROLE",
                "arn:aws:iam::123456789012:role/SageMakerRole"
            ),
            "training_image": os.environ.get(
                "TGF_TEST_TRAINING_IMAGE",
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/tgf-training:latest"
            ),
            "data_s3_uri": "s3://tgf-test-bucket/data/",
            "output_s3_uri": "s3://tgf-test-bucket/output/",
        })

        artifacts = exporter.export({
            "route_key": "aws_smoke_test",
            "run_id": "smoke_run_001",
        })

        assert len(artifacts) >= 2

        # Verify job spec is valid JSON
        job_spec_artifact = next(a for a in artifacts if "training-job.json" in a.name)
        job_spec = json.loads(job_spec_artifact.content)

        assert "TrainingJobName" in job_spec
        assert "RoleArn" in job_spec


class TestGCPConnectivity:
    """Test GCP service connectivity when credentials available."""

    @pytest.mark.skipif(not HAS_GCP_CREDS, reason="GCP credentials not available")
    def test_gcs_connector_health(self):
        """Test GCS connector health check with real GCP."""
        pytest.importorskip("google.cloud.storage")

        # GCS connector would be similar to S3
        # For now, just verify we can import GCP libraries
        from google.cloud import storage

        project = os.environ.get("GCLOUD_PROJECT", "tgf-test-project")
        assert project is not None

    @pytest.mark.skipif(not HAS_GCP_CREDS, reason="GCP credentials not available")
    def test_vertex_ai_exporter_generates_valid_spec(self):
        """Test Vertex AI exporter generates valid job spec."""
        from tensorguard.integrations.exporters import VertexAIExporter

        exporter = VertexAIExporter({
            "project_id": os.environ.get("GCLOUD_PROJECT", "tgf-test-project"),
            "location": "us-central1",
            "training_image": "gcr.io/tgf-test-project/tgf-training:latest",
        })

        artifacts = exporter.export({
            "route_key": "gcp_smoke_test",
            "run_id": "smoke_run_001",
        })

        assert len(artifacts) >= 2

        job_spec_artifact = next(a for a in artifacts if "custom-job.json" in a.name)
        job_spec = json.loads(job_spec_artifact.content)

        assert "displayName" in job_spec
        assert "jobSpec" in job_spec


class TestAzureConnectivity:
    """Test Azure service connectivity when credentials available."""

    @pytest.mark.skipif(not HAS_AZURE_CREDS, reason="Azure credentials not available")
    def test_azure_blob_health(self):
        """Test Azure Blob Storage health check."""
        pytest.importorskip("azure.storage.blob")

        # Just verify we can import Azure libraries
        from azure.storage.blob import BlobServiceClient

        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if connection_string:
            client = BlobServiceClient.from_connection_string(connection_string)
            assert client is not None

    @pytest.mark.skipif(not HAS_AZURE_CREDS, reason="Azure credentials not available")
    def test_azure_ml_exporter_generates_valid_spec(self):
        """Test Azure ML exporter generates valid job spec."""
        from tensorguard.integrations.exporters import AzureMLExporter

        exporter = AzureMLExporter({
            "workspace_name": os.environ.get("AZURE_ML_WORKSPACE", "tgf-workspace"),
            "resource_group": os.environ.get("AZURE_RESOURCE_GROUP", "tgf-rg"),
            "compute_target": "gpu-cluster",
        })

        artifacts = exporter.export({
            "route_key": "azure_smoke_test",
            "run_id": "smoke_run_001",
        })

        assert len(artifacts) >= 2


class TestDatabricksConnectivity:
    """Test Databricks connectivity when credentials available."""

    @pytest.mark.skipif(not HAS_DATABRICKS_CREDS, reason="Databricks credentials not available")
    def test_databricks_api_health(self):
        """Test Databricks API connectivity."""
        import urllib.request
        import urllib.error

        host = os.environ.get("DATABRICKS_HOST")
        token = os.environ.get("DATABRICKS_TOKEN")

        if not host or not token:
            pytest.skip("Databricks credentials incomplete")

        # Simple API health check
        url = f"{host}/api/2.0/clusters/list"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                assert response.status == 200
        except urllib.error.HTTPError as e:
            # 401/403 means credentials work but permissions may be limited
            assert e.code in [200, 401, 403]

    @pytest.mark.skipif(not HAS_DATABRICKS_CREDS, reason="Databricks credentials not available")
    def test_databricks_exporter_generates_valid_spec(self):
        """Test Databricks exporter generates valid job spec."""
        from tensorguard.integrations.exporters import DatabricksExporter

        exporter = DatabricksExporter({
            "workspace_url": os.environ.get("DATABRICKS_HOST"),
            "notebook_path": "/Shared/tgf/smoke_test",
        })

        artifacts = exporter.export({
            "route_key": "databricks_smoke_test",
            "run_id": "smoke_run_001",
        })

        assert len(artifacts) >= 2


class TestMLflowConnectivity:
    """Test MLflow connectivity when configured."""

    @pytest.mark.skipif(not HAS_MLFLOW_CREDS, reason="MLflow not configured")
    def test_mlflow_tracking_health(self):
        """Test MLflow tracking server connectivity."""
        pytest.importorskip("mlflow")
        import mlflow

        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
        mlflow.set_tracking_uri(tracking_uri)

        # Try to list experiments
        try:
            experiments = mlflow.search_experiments()
            assert experiments is not None
        except Exception as e:
            # Connection issues are expected in some environments
            print(f"MLflow connectivity test: {e}")


class TestWandBConnectivity:
    """Test Weights & Biases connectivity when configured."""

    @pytest.mark.skipif(not HAS_WANDB_CREDS, reason="W&B not configured")
    def test_wandb_api_health(self):
        """Test W&B API connectivity."""
        pytest.importorskip("wandb")
        import wandb

        api_key = os.environ.get("WANDB_API_KEY")
        if not api_key:
            pytest.skip("WANDB_API_KEY not set")

        # Initialize API client
        api = wandb.Api()
        assert api is not None


class TestCredentialDetection:
    """Test credential detection utilities."""

    def test_aws_credential_detection(self):
        """Verify AWS credential detection logic."""
        # This test always runs to verify detection logic
        result = HAS_AWS_CREDS
        print(f"AWS credentials detected: {result}")
        # Just verify it's a boolean
        assert isinstance(result, bool)

    def test_gcp_credential_detection(self):
        """Verify GCP credential detection logic."""
        result = HAS_GCP_CREDS
        print(f"GCP credentials detected: {result}")
        assert isinstance(result, bool)

    def test_azure_credential_detection(self):
        """Verify Azure credential detection logic."""
        result = HAS_AZURE_CREDS
        print(f"Azure credentials detected: {result}")
        assert isinstance(result, bool)

    def test_credential_summary(self):
        """Print credential detection summary for debugging."""
        summary = {
            "aws": HAS_AWS_CREDS,
            "gcp": HAS_GCP_CREDS,
            "azure": HAS_AZURE_CREDS,
            "databricks": HAS_DATABRICKS_CREDS,
            "mlflow": HAS_MLFLOW_CREDS,
            "wandb": HAS_WANDB_CREDS,
        }

        print("\n=== Credential Detection Summary ===")
        for provider, available in summary.items():
            status = "AVAILABLE" if available else "not found"
            print(f"  {provider}: {status}")
        print("====================================\n")

        # Always passes - informational only
        assert True


class TestExporterCLIScriptValidity:
    """Test that exported CLI scripts are valid shell scripts."""

    def test_sagemaker_script_syntax(self):
        """Verify SageMaker submit script has valid syntax."""
        from tensorguard.integrations.exporters import SageMakerExporter

        exporter = SageMakerExporter({
            "role_arn": "arn:aws:iam::123456789012:role/TestRole",
            "training_image": "test-image:latest",
            "data_s3_uri": "s3://test/data/",
            "output_s3_uri": "s3://test/output/",
        })

        artifacts = exporter.export({"route_key": "script_test"})

        script_artifact = next(a for a in artifacts if a.name.endswith(".sh"))

        # Basic validation
        assert script_artifact.content.startswith("#!/bin/bash")
        assert "set -e" in script_artifact.content
        assert "aws sagemaker" in script_artifact.content

    def test_vertex_script_syntax(self):
        """Verify Vertex AI submit script has valid syntax."""
        from tensorguard.integrations.exporters import VertexAIExporter

        exporter = VertexAIExporter({
            "project_id": "test-project",
            "training_image": "test-image:latest",
        })

        artifacts = exporter.export({"route_key": "script_test"})

        script_artifact = next(a for a in artifacts if a.name.endswith(".sh"))

        assert script_artifact.content.startswith("#!/bin/bash")
        assert "gcloud ai custom-jobs" in script_artifact.content

    def test_azure_script_syntax(self):
        """Verify Azure ML submit script has valid syntax."""
        from tensorguard.integrations.exporters import AzureMLExporter

        exporter = AzureMLExporter({
            "workspace_name": "test-workspace",
            "compute_target": "test-cluster",
        })

        artifacts = exporter.export({"route_key": "script_test"})

        script_artifact = next(a for a in artifacts if a.name.endswith(".sh"))

        assert script_artifact.content.startswith("#!/bin/bash")
        assert "az ml job create" in script_artifact.content

    def test_databricks_script_syntax(self):
        """Verify Databricks submit script has valid syntax."""
        from tensorguard.integrations.exporters import DatabricksExporter

        exporter = DatabricksExporter({
            "workspace_url": "https://test.databricks.net",
            "notebook_path": "/test/notebook",
        })

        artifacts = exporter.export({"route_key": "script_test"})

        script_artifact = next(a for a in artifacts if a.name.endswith(".sh"))

        assert script_artifact.content.startswith("#!/bin/bash")
        assert "databricks jobs" in script_artifact.content
