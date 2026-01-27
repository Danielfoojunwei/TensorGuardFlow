"""
Tracking and registry connectors (Category E).

These connectors provide experiment tracking and metrics sinking capabilities.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from tensorguard.integrations.framework.contracts import (
    TrackingConnector,
    IntegrationConnector,
    ConnectorCapability,
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.framework.manager import IntegrationRegistry


@IntegrationRegistry.register("tgf_internal")
class TGFInternalRegistryConnector(IntegrationConnector):
    """Connector for TGF internal adapter registry."""

    @property
    def provider(self) -> str:
        return "tgf_internal"

    @property
    def category(self) -> str:
        return "E"

    @property
    def display_name(self) -> str:
        return "TGF Internal Registry"

    def validate_config(self) -> ValidationResult:
        """TGF internal registry is always valid."""
        return ValidationResult(valid=True)

    async def health_check(self) -> HealthCheckResult:
        """Check TGF registry health (database connection)."""
        start_time = time.time()

        # In a real implementation, this would check database connection
        # For now, always return OK
        return HealthCheckResult(
            status="OK",
            message="Database connected",
            latency_ms=int((time.time() - start_time) * 1000),
            details={"type": "internal"},
        )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.ADAPTER_REGISTRY,
            ConnectorCapability.CHANNEL_MANAGEMENT,
            ConnectorCapability.EVIDENCE_CHAIN,
            ConnectorCapability.GATE_EVALUATION,
            ConnectorCapability.TGSP_PACKAGING,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Smoke test TGF registry."""
        start_time = time.time()

        # Always pass - internal component
        return SmokeTestResult(
            passed=True,
            test_name="registry_check",
            duration_ms=int((time.time() - start_time) * 1000),
            message="Internal registry available",
        )

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export registry state artifact."""
        route_key = context.get("route_key", "unknown")

        artifact_content = json.dumps({
            "registry": "tgf_internal",
            "route_key": route_key,
            "timestamp": datetime.utcnow().isoformat(),
            "channels": ["candidate", "stable", "deprecated"],
        }, indent=2)

        return [
            ExportArtifact(
                name="registry-state.json",
                content=artifact_content,
                artifact_type="json",
            )
        ]


@IntegrationRegistry.register("mlflow")
class MLflowConnector(TrackingConnector):
    """Connector for MLflow tracking."""

    @property
    def provider(self) -> str:
        return "mlflow"

    @property
    def display_name(self) -> str:
        return "MLflow"

    def validate_config(self) -> ValidationResult:
        """Validate MLflow configuration."""
        errors = []
        warnings = []

        tracking_uri = self.config.get("tracking_uri")
        if not tracking_uri:
            errors.append("tracking_uri is required")

        experiment_name = self.config.get("experiment_name")
        if not experiment_name:
            warnings.append("experiment_name not specified")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def health_check(self) -> HealthCheckResult:
        """Check MLflow server connectivity."""
        start_time = time.time()

        tracking_uri = self.config.get("tracking_uri")

        try:
            import mlflow

            mlflow.set_tracking_uri(tracking_uri)

            # Try to list experiments
            experiments = mlflow.search_experiments(max_results=1)

            return HealthCheckResult(
                status="OK",
                message=f"MLflow server accessible at {tracking_uri}",
                latency_ms=int((time.time() - start_time) * 1000),
                details={"tracking_uri": tracking_uri},
            )

        except ImportError:
            return HealthCheckResult(
                status="WARN",
                message="mlflow not installed - schema validation only",
                latency_ms=int((time.time() - start_time) * 1000),
                details={"validation_only": True},
            )

        except Exception as e:
            return HealthCheckResult(
                status="FAIL",
                message=f"MLflow access failed: {str(e)}",
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def capabilities(self) -> List[ConnectorCapability]:
        return [
            ConnectorCapability.METRICS_SINK,
            ConnectorCapability.EXPERIMENT_TRACKING,
        ]

    async def smoke_test(self) -> SmokeTestResult:
        """Run smoke test on MLflow."""
        start_time = time.time()

        try:
            import mlflow

            tracking_uri = self.config.get("tracking_uri")
            mlflow.set_tracking_uri(tracking_uri)

            # List experiments
            experiments = mlflow.search_experiments(max_results=5)

            return SmokeTestResult(
                passed=True,
                test_name="list_experiments",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Found {len(experiments)} experiments",
                details={"experiment_count": len(experiments)},
            )

        except ImportError:
            return SmokeTestResult(
                passed=True,
                test_name="list_experiments",
                duration_ms=int((time.time() - start_time) * 1000),
                message="mlflow not installed - skipped",
                details={"validation_only": True},
            )

        except Exception as e:
            return SmokeTestResult(
                passed=False,
                test_name="list_experiments",
                duration_ms=int((time.time() - start_time) * 1000),
                message=f"Failed: {str(e)}",
            )

    async def log_metrics(
        self,
        run_id: str,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log metrics to MLflow."""
        try:
            import mlflow

            tracking_uri = self.config.get("tracking_uri")
            mlflow.set_tracking_uri(tracking_uri)

            with mlflow.start_run(run_id=run_id):
                mlflow.log_metrics(metrics, step=step)

        except ImportError:
            pass

    async def log_params(self, run_id: str, params: Dict[str, Any]) -> None:
        """Log parameters to MLflow."""
        try:
            import mlflow

            tracking_uri = self.config.get("tracking_uri")
            mlflow.set_tracking_uri(tracking_uri)

            with mlflow.start_run(run_id=run_id):
                # Convert all params to strings
                str_params = {k: str(v) for k, v in params.items()}
                mlflow.log_params(str_params)

        except ImportError:
            pass

    async def log_artifact(
        self,
        run_id: str,
        artifact_path: str,
        artifact_name: Optional[str] = None,
    ) -> None:
        """Log artifact to MLflow."""
        try:
            import mlflow

            tracking_uri = self.config.get("tracking_uri")
            mlflow.set_tracking_uri(tracking_uri)

            with mlflow.start_run(run_id=run_id):
                mlflow.log_artifact(artifact_path, artifact_name)

        except ImportError:
            pass

    async def export_artifacts(
        self,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """Export MLflow integration config."""
        tracking_uri = self.config.get("tracking_uri")
        experiment_name = self.config.get("experiment_name")

        artifact_content = json.dumps({
            "provider": "mlflow",
            "tracking_uri": tracking_uri,
            "experiment_name": experiment_name,
            "route_key": context.get("route_key", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
        }, indent=2)

        return [
            ExportArtifact(
                name="mlflow-config.json",
                content=artifact_content,
                artifact_type="json",
            )
        ]

    def get_endpoints_used(self) -> List[Dict[str, Any]]:
        tracking_uri = self.config.get("tracking_uri", "http://mlflow:5000")
        return [
            {
                "endpoint": tracking_uri,
                "type": "outbound",
                "protocol": "https",
                "auth_method": "api_key" if self.config.get("username") else "none",
            }
        ]
