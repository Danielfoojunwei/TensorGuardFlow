"""
Integration manager for TensorGuardFlow.

This module provides the IntegrationManager class that manages
the integration graph for tenants, including:
- Loading and storing integration configurations
- Running health checks across all integrations
- Building topology snapshots
- Coordinating export artifact generation
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel

from tensorguard.integrations.framework.contracts import (
    IntegrationConnector,
    HealthCheckResult,
    ValidationResult,
    SmokeTestResult,
    ExportArtifact,
)
from tensorguard.integrations.framework.config_schema import (
    IntegrationCategory,
    IntegrationConfig,
    NodeStatus,
    EdgeProtocol,
    PROVIDER_REGISTRY,
    get_config_class,
)
from tensorguard.integrations.framework.topology import (
    IntegrationTopology,
    IntegrationNode,
    IntegrationEdge,
    TopologySummary,
    TopologyBuilder,
    EndpointUsage,
    ArtifactInfo,
    EndpointType,
)

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Registry of available integration connectors.

    This class maintains a mapping of provider names to connector classes,
    allowing dynamic registration and lookup of connectors.
    """

    _connectors: Dict[str, Type[IntegrationConnector]] = {}

    @classmethod
    def register(cls, provider: str) -> Callable:
        """
        Decorator to register a connector class.

        Usage:
            @IntegrationRegistry.register("aws_s3")
            class S3Connector(DataSourceConnector):
                ...
        """
        def decorator(connector_class: Type[IntegrationConnector]) -> Type[IntegrationConnector]:
            cls._connectors[provider] = connector_class
            return connector_class
        return decorator

    @classmethod
    def get_connector_class(cls, provider: str) -> Optional[Type[IntegrationConnector]]:
        """Get the connector class for a provider."""
        return cls._connectors.get(provider)

    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered providers."""
        return list(cls._connectors.keys())

    @classmethod
    def create_connector(
        cls,
        provider: str,
        config: Dict[str, Any],
    ) -> IntegrationConnector:
        """Create a connector instance for a provider."""
        connector_class = cls.get_connector_class(provider)
        if connector_class is None:
            raise ValueError(f"No connector registered for provider: {provider}")
        return connector_class(config)


class IntegrationManager:
    """
    Manages the integration graph for a tenant.

    This class is responsible for:
    - Storing and loading integration configurations
    - Creating and managing connector instances
    - Running health checks and smoke tests
    - Building topology snapshots
    - Coordinating export artifact generation
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._configs: Dict[str, IntegrationConfig] = {}
        self._connectors: Dict[str, IntegrationConnector] = {}
        self._topology: Optional[IntegrationTopology] = None
        self._last_health_check: Optional[datetime] = None

    def configure(
        self,
        id: str,
        category: IntegrationCategory,
        provider: str,
        config: Dict[str, Any],
        enabled: bool = True,
    ) -> ValidationResult:
        """
        Configure an integration.

        Args:
            id: Unique identifier for this integration
            category: Integration category (C, D, E, F, or G)
            provider: Provider name (e.g., 'aws_s3', 'kubernetes')
            config: Provider-specific configuration
            enabled: Whether the integration is enabled

        Returns:
            ValidationResult indicating success/failure
        """
        # Validate provider exists
        if provider not in PROVIDER_REGISTRY:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown provider: {provider}"],
                suggestions=[f"Available providers: {list(PROVIDER_REGISTRY.keys())}"],
            )

        # Validate category matches provider
        expected_category, config_class = PROVIDER_REGISTRY[provider]
        if category != expected_category:
            return ValidationResult(
                valid=False,
                errors=[
                    f"Provider '{provider}' belongs to category {expected_category.value}, "
                    f"not {category.value}"
                ],
            )

        # Validate configuration
        try:
            validated_config = config_class(**config)
        except Exception as e:
            return ValidationResult(
                valid=False,
                errors=[f"Configuration validation failed: {str(e)}"],
            )

        # Create integration config
        integration_config = IntegrationConfig(
            id=id,
            category=category,
            provider=provider,
            enabled=enabled,
            config=config,
        )

        # Try to create connector
        connector_class = IntegrationRegistry.get_connector_class(provider)
        if connector_class:
            try:
                connector = connector_class(config)
                validation = connector.validate_config()
                if not validation.valid:
                    return validation
                self._connectors[id] = connector
            except Exception as e:
                return ValidationResult(
                    valid=False,
                    errors=[f"Failed to create connector: {str(e)}"],
                )

        # Store configuration
        self._configs[id] = integration_config

        # Invalidate topology cache
        self._topology = None

        return ValidationResult(valid=True)

    def get_config(self, id: str) -> Optional[IntegrationConfig]:
        """Get an integration configuration by ID."""
        return self._configs.get(id)

    def list_configs(
        self,
        category: Optional[IntegrationCategory] = None,
    ) -> List[IntegrationConfig]:
        """List all integration configurations, optionally filtered by category."""
        configs = list(self._configs.values())
        if category:
            configs = [c for c in configs if c.category == category]
        return configs

    def remove(self, id: str) -> bool:
        """Remove an integration configuration."""
        if id not in self._configs:
            return False
        del self._configs[id]
        if id in self._connectors:
            del self._connectors[id]
        self._topology = None
        return True

    def get_connector(self, id: str) -> Optional[IntegrationConnector]:
        """Get a connector instance by integration ID."""
        return self._connectors.get(id)

    async def health_check(self, id: str) -> HealthCheckResult:
        """
        Run a health check on a specific integration.

        Args:
            id: Integration ID

        Returns:
            HealthCheckResult with status and details
        """
        connector = self._connectors.get(id)
        if connector is None:
            return HealthCheckResult(
                status="FAIL",
                message=f"No connector found for integration: {id}",
                latency_ms=0,
            )

        try:
            return await connector.health_check()
        except Exception as e:
            logger.exception(f"Health check failed for {id}")
            return HealthCheckResult(
                status="FAIL",
                message=f"Health check error: {str(e)}",
                latency_ms=0,
            )

    async def health_check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Run health checks on all integrations concurrently.

        Returns:
            Dict mapping integration ID to HealthCheckResult
        """
        results = {}
        tasks = []

        for id, connector in self._connectors.items():
            config = self._configs.get(id)
            if config and not config.enabled:
                results[id] = HealthCheckResult(
                    status="DISABLED",
                    message="Integration is disabled",
                    latency_ms=0,
                )
                continue
            tasks.append((id, connector.health_check()))

        if tasks:
            task_results = await asyncio.gather(
                *[t[1] for t in tasks],
                return_exceptions=True,
            )
            for (id, _), result in zip(tasks, task_results):
                if isinstance(result, Exception):
                    results[id] = HealthCheckResult(
                        status="FAIL",
                        message=f"Health check error: {str(result)}",
                        latency_ms=0,
                    )
                else:
                    results[id] = result

        self._last_health_check = datetime.utcnow()
        return results

    async def smoke_test(self, id: str) -> SmokeTestResult:
        """
        Run a smoke test on a specific integration.

        Args:
            id: Integration ID

        Returns:
            SmokeTestResult with pass/fail and details
        """
        connector = self._connectors.get(id)
        if connector is None:
            return SmokeTestResult(
                passed=False,
                test_name="smoke_test",
                duration_ms=0,
                message=f"No connector found for integration: {id}",
            )

        try:
            return await connector.smoke_test()
        except Exception as e:
            logger.exception(f"Smoke test failed for {id}")
            return SmokeTestResult(
                passed=False,
                test_name="smoke_test",
                duration_ms=0,
                message=f"Smoke test error: {str(e)}",
            )

    async def smoke_test_all(self) -> Dict[str, SmokeTestResult]:
        """
        Run smoke tests on all integrations concurrently.

        Returns:
            Dict mapping integration ID to SmokeTestResult
        """
        results = {}
        tasks = []

        for id, connector in self._connectors.items():
            config = self._configs.get(id)
            if config and not config.enabled:
                results[id] = SmokeTestResult(
                    passed=True,
                    test_name="smoke_test",
                    duration_ms=0,
                    message="Skipped - integration disabled",
                )
                continue
            tasks.append((id, connector.smoke_test()))

        if tasks:
            task_results = await asyncio.gather(
                *[t[1] for t in tasks],
                return_exceptions=True,
            )
            for (id, _), result in zip(tasks, task_results):
                if isinstance(result, Exception):
                    results[id] = SmokeTestResult(
                        passed=False,
                        test_name="smoke_test",
                        duration_ms=0,
                        message=f"Smoke test error: {str(result)}",
                    )
                else:
                    results[id] = result

        return results

    async def export_artifacts(
        self,
        target: str,
        context: Dict[str, Any],
    ) -> List[ExportArtifact]:
        """
        Generate export artifacts for a target platform.

        Args:
            target: Target platform (e.g., 'kubernetes', 'vllm', 'sagemaker')
            context: Context with route_key, adapter info, etc.

        Returns:
            List of ExportArtifact objects
        """
        # Find connector for target
        connector = None
        for id, c in self._connectors.items():
            if c.provider == target:
                connector = c
                break

        if connector is None:
            # Try to create a temporary connector for export
            connector_class = IntegrationRegistry.get_connector_class(target)
            if connector_class is None:
                raise ValueError(f"No connector available for target: {target}")
            connector = connector_class({})

        return await connector.export_artifacts(context)

    def build_topology(
        self,
        include_health: bool = True,
    ) -> IntegrationTopology:
        """
        Build a topology snapshot.

        Args:
            include_health: Whether to include health check results

        Returns:
            IntegrationTopology object
        """
        builder = TopologyBuilder(self.tenant_id)

        # Add nodes for each configured integration
        for id, config in self._configs.items():
            connector = self._connectors.get(id)
            last_health = connector.get_last_health_check() if connector else None

            # Determine status
            if not config.enabled:
                status = NodeStatus.DISABLED
                status_message = "Integration disabled"
            elif last_health:
                status = NodeStatus(last_health.status)
                status_message = last_health.message
            else:
                status = NodeStatus.UNKNOWN
                status_message = "No health check performed"

            # Get provider display name
            provider_display = config.provider.replace("_", " ").title()
            if connector:
                provider_display = connector.display_name

            # Get capabilities
            capabilities = []
            if connector:
                capabilities = [c.value for c in connector.capabilities()]

            # Get endpoints
            endpoints_used = []
            if connector:
                for ep in connector.get_endpoints_used():
                    endpoints_used.append(EndpointUsage(**ep))

            # Add node based on category
            node = IntegrationNode(
                id=id,
                category=config.category,
                provider=config.provider,
                provider_display=provider_display,
                status=status,
                status_message=status_message,
                last_health_check=last_health.timestamp if last_health else None,
                health_check_latency_ms=last_health.latency_ms if last_health else None,
                capabilities=capabilities,
                endpoints_used=endpoints_used,
                config_fingerprint=config.compute_fingerprint(),
                enabled=config.enabled,
            )
            builder.nodes.append(node)

        # Ensure there's always a TGF internal registry node
        if not any(n.provider == "tgf_internal" for n in builder.nodes):
            builder.add_registry()

        # Build standard edges based on category flow
        node_by_category: Dict[str, List[str]] = {
            "C": [],
            "D": [],
            "E": [],
            "F": [],
            "G": [],
        }
        for node in builder.nodes:
            cat = node.category.value if hasattr(node.category, "value") else node.category
            node_by_category[cat].append(node.id)

        # C -> D (data to training)
        for c_id in node_by_category["C"]:
            for d_id in node_by_category["D"]:
                builder.connect(
                    c_id, d_id,
                    EdgeProtocol.FILE,
                    data_types=["training_data"],
                )

        # D -> E (training to registry)
        for d_id in node_by_category["D"]:
            for e_id in node_by_category["E"]:
                builder.connect(
                    d_id, e_id,
                    EdgeProtocol.API,
                    data_types=["adapter_weights", "metrics", "evidence"],
                )

        # E -> F (registry to serving)
        for e_id in node_by_category["E"]:
            if "tgf_internal" in e_id or e_id == "tgf-registry":
                for f_id in node_by_category["F"]:
                    builder.connect(
                        e_id, f_id,
                        EdgeProtocol.EXPORT,
                        data_types=["serving_config", "adapter_reference"],
                    )
                    # Also add reverse edge for /resolve
                    builder.connect(
                        f_id, e_id,
                        EdgeProtocol.API,
                        data_types=["resolve_request"],
                        notes="Runtime calls /resolve endpoint",
                    )

        # E -> G (registry to trust)
        for e_id in node_by_category["E"]:
            if "tgf_internal" in e_id or e_id == "tgf-registry":
                for g_id in node_by_category["G"]:
                    builder.connect(
                        e_id, g_id,
                        EdgeProtocol.API,
                        data_types=["sign_request", "verify_request"],
                    )

        return builder.build()

    async def get_topology(
        self,
        force_refresh: bool = False,
    ) -> IntegrationTopology:
        """
        Get the current topology, optionally refreshing health checks.

        Args:
            force_refresh: Force health check refresh

        Returns:
            IntegrationTopology object
        """
        if force_refresh or self._topology is None:
            # Run health checks
            await self.health_check_all()
            # Build topology
            self._topology = self.build_topology(include_health=True)

        return self._topology

    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get aggregate capabilities across all integrations.

        Returns:
            Dict mapping capability name to availability
        """
        capabilities = {
            "supports_k8s_export": False,
            "supports_sagemaker_export": False,
            "supports_vertex_export": False,
            "supports_azureml_export": False,
            "supports_databricks_export": False,
            "supports_vllm_pack": False,
            "supports_tgi_pack": False,
            "supports_triton_pack": False,
            "supports_kms_signing": False,
            "supports_vault_signing": False,
            "supports_nitro_enclave": False,
            "supports_n2he": False,
            "supports_mlflow_export": False,
            "supports_wandb_export": False,
        }

        for config in self._configs.values():
            if not config.enabled:
                continue
            provider = config.provider

            if provider == "kubernetes":
                capabilities["supports_k8s_export"] = True
            elif provider == "sagemaker":
                capabilities["supports_sagemaker_export"] = True
            elif provider == "vertex_ai":
                capabilities["supports_vertex_export"] = True
            elif provider == "azure_ml":
                capabilities["supports_azureml_export"] = True
            elif provider == "databricks":
                capabilities["supports_databricks_export"] = True
            elif provider == "vllm":
                capabilities["supports_vllm_pack"] = True
            elif provider == "tgi":
                capabilities["supports_tgi_pack"] = True
            elif provider == "triton":
                capabilities["supports_triton_pack"] = True
            elif provider == "aws_kms":
                capabilities["supports_kms_signing"] = True
            elif provider == "vault_transit":
                capabilities["supports_vault_signing"] = True
            elif provider == "nitro_enclave":
                capabilities["supports_nitro_enclave"] = True
            elif provider == "n2he":
                capabilities["supports_n2he"] = True
            elif provider == "mlflow":
                capabilities["supports_mlflow_export"] = True
            elif provider == "wandb":
                capabilities["supports_wandb_export"] = True

        return capabilities

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager state to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "configs": {
                id: config.model_dump()
                for id, config in self._configs.items()
            },
            "last_health_check": (
                self._last_health_check.isoformat()
                if self._last_health_check
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntegrationManager":
        """Deserialize manager state from dictionary."""
        manager = cls(data["tenant_id"])
        for id, config_data in data.get("configs", {}).items():
            config = IntegrationConfig(**config_data)
            manager._configs[id] = config

            # Try to create connector
            connector_class = IntegrationRegistry.get_connector_class(config.provider)
            if connector_class:
                try:
                    manager._connectors[id] = connector_class(config.config)
                except Exception:
                    pass

        if data.get("last_health_check"):
            manager._last_health_check = datetime.fromisoformat(
                data["last_health_check"]
            )

        return manager
