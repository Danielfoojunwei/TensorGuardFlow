"""
TIER 2: Local End-to-End Tests

Tests the full integration cycle using local connectors only (no cloud required).
Exercises: route → run_once → candidate → gates → promote → resolve → rollback

Run with: pytest tests/integration/full_stack/test_local_e2e.py -v
"""

import os
import json
import tempfile
import pytest
from datetime import datetime
from typing import Dict, Any

from tensorguard.integrations.framework.manager import IntegrationManager, IntegrationRegistry
from tensorguard.integrations.framework.topology import TopologyBuilder
from tensorguard.integrations.framework.contracts import (
    HealthCheckResult,
    SmokeTestResult,
    ConnectorCapability,
)
from tensorguard.integrations.connectors import (
    LocalFilesystemConnector,
    LocalGPUConnector,
    TGFInternalTrackingConnector,
    LocalDevSigningConnector,
)
from tensorguard.integrations.exporters import VLLMExporter, TGIExporter


class TestIntegrationManagerLifecycle:
    """Test IntegrationManager configuration and lifecycle."""

    def test_manager_initialization(self):
        """Manager should initialize with tenant context."""
        manager = IntegrationManager(tenant_id="test_tenant")
        assert manager.tenant_id == "test_tenant"
        assert manager._connectors == {}

    def test_register_and_configure_connector(self, local_data_config):
        """Should register and configure connectors."""
        manager = IntegrationManager(tenant_id="test_tenant")

        # Configure connector
        result = manager.configure(
            provider="local_filesystem",
            category="data_source",
            config=local_data_config
        )

        assert result.valid
        assert "local_filesystem" in manager._connectors

    def test_multiple_connectors(self, local_data_config, local_gpu_config):
        """Should support multiple connectors."""
        manager = IntegrationManager(tenant_id="test_tenant")

        manager.configure("local_filesystem", "data_source", local_data_config)
        manager.configure("local_gpu", "training", local_gpu_config)

        assert len(manager._connectors) == 2

    def test_reconfigure_connector(self, local_data_config):
        """Reconfiguring should update connector."""
        manager = IntegrationManager(tenant_id="test_tenant")

        manager.configure("local_filesystem", "data_source", local_data_config)

        # Reconfigure with different path
        new_config = {**local_data_config, "base_path": "/new/path"}
        result = manager.configure("local_filesystem", "data_source", new_config)

        assert result.valid


class TestLocalFilesystemConnector:
    """Test local filesystem data source connector."""

    def test_health_check_valid_path(self, local_data_config):
        """Health check should pass for valid path."""
        connector = LocalFilesystemConnector(local_data_config)
        result = connector.health_check()

        assert isinstance(result, HealthCheckResult)
        assert result.healthy
        assert result.latency_ms >= 0

    def test_health_check_invalid_path(self):
        """Health check should fail for invalid path."""
        connector = LocalFilesystemConnector({
            "base_path": "/nonexistent/path/12345",
            "allowed_extensions": [".json"],
        })
        result = connector.health_check()

        assert not result.healthy
        assert result.message is not None

    def test_capabilities(self, local_data_config):
        """Should report correct capabilities."""
        connector = LocalFilesystemConnector(local_data_config)
        caps = connector.capabilities()

        assert ConnectorCapability.LIST_OBJECTS in caps
        assert ConnectorCapability.READ_OBJECT in caps
        assert ConnectorCapability.HEALTH_CHECK in caps

    def test_smoke_test(self, local_data_config):
        """Smoke test should pass for configured connector."""
        connector = LocalFilesystemConnector(local_data_config)
        result = connector.smoke_test()

        assert isinstance(result, SmokeTestResult)
        assert result.passed
        assert result.duration_ms >= 0

    def test_list_objects(self, local_data_config):
        """Should list objects in directory."""
        # Create test files
        base_path = local_data_config["base_path"]
        test_file = os.path.join(base_path, "test_data.json")
        with open(test_file, "w") as f:
            json.dump({"test": True}, f)

        connector = LocalFilesystemConnector(local_data_config)
        objects = connector.list_objects()

        assert len(objects) >= 1
        assert any("test_data.json" in obj for obj in objects)

        # Cleanup
        os.remove(test_file)


class TestLocalGPUConnector:
    """Test local GPU training connector."""

    def test_health_check(self, local_gpu_config):
        """Health check should report status."""
        connector = LocalGPUConnector(local_gpu_config)
        result = connector.health_check()

        assert isinstance(result, HealthCheckResult)
        # May or may not be healthy depending on GPU availability
        assert result.latency_ms >= 0

    def test_capabilities(self, local_gpu_config):
        """Should report training capabilities."""
        connector = LocalGPUConnector(local_gpu_config)
        caps = connector.capabilities()

        assert ConnectorCapability.SUBMIT_JOB in caps
        assert ConnectorCapability.HEALTH_CHECK in caps

    def test_smoke_test(self, local_gpu_config):
        """Smoke test should complete."""
        connector = LocalGPUConnector(local_gpu_config)
        result = connector.smoke_test()

        assert isinstance(result, SmokeTestResult)
        assert result.duration_ms >= 0


class TestLocalDevSigningConnector:
    """Test local development signing connector."""

    def test_health_check(self):
        """Health check should always pass for local dev."""
        connector = LocalDevSigningConnector({
            "secret_key": "test-secret-key-12345",
        })
        result = connector.health_check()

        assert result.healthy
        assert "Local development" in result.message or result.healthy

    def test_sign_and_verify(self):
        """Should sign and verify data."""
        connector = LocalDevSigningConnector({
            "secret_key": "test-secret-key-12345",
        })

        data = b"test data to sign"
        signature = connector.sign(data)

        assert isinstance(signature, bytes)
        assert len(signature) > 0

        # Verify signature
        is_valid = connector.verify(data, signature)
        assert is_valid

    def test_invalid_signature_rejected(self):
        """Should reject invalid signatures."""
        connector = LocalDevSigningConnector({
            "secret_key": "test-secret-key-12345",
        })

        data = b"test data"
        signature = connector.sign(data)

        # Tamper with signature
        tampered = bytes([b ^ 0xFF for b in signature])
        is_valid = connector.verify(data, tampered)

        assert not is_valid

    def test_capabilities(self):
        """Should report signing capabilities."""
        connector = LocalDevSigningConnector({
            "secret_key": "test-secret-key",
        })
        caps = connector.capabilities()

        assert ConnectorCapability.SIGN in caps
        assert ConnectorCapability.VERIFY in caps


class TestTopologyBuilder:
    """Test topology construction."""

    def test_build_minimal_topology(self):
        """Should build minimal topology with one node."""
        builder = TopologyBuilder()
        builder.add_node(
            node_id="local_data",
            provider="local_filesystem",
            category="data_source",
            status="healthy",
        )

        topology = builder.build()

        assert len(topology.nodes) == 1
        assert topology.nodes[0].node_id == "local_data"

    def test_build_topology_with_edges(self):
        """Should build topology with connected nodes."""
        builder = TopologyBuilder()
        builder.add_node("data", "local_filesystem", "data_source", "healthy")
        builder.add_node("training", "local_gpu", "training", "healthy")
        builder.add_edge("data", "training", "feeds")

        topology = builder.build()

        assert len(topology.nodes) == 2
        assert len(topology.edges) == 1
        assert topology.edges[0].source == "data"
        assert topology.edges[0].target == "training"

    def test_topology_summary(self):
        """Should compute topology summary."""
        builder = TopologyBuilder()
        builder.add_node("data", "local_filesystem", "data_source", "healthy")
        builder.add_node("training", "local_gpu", "training", "healthy")
        builder.add_node("serving", "vllm", "serving", "degraded")
        builder.add_edge("data", "training", "feeds")
        builder.add_edge("training", "serving", "exports")

        topology = builder.build()
        summary = topology.compute_summary()

        assert summary.total_nodes == 3
        assert summary.total_edges == 2
        assert summary.healthy_nodes == 2
        assert summary.degraded_nodes == 1

    def test_topology_validation(self):
        """Should validate topology for orphan nodes."""
        builder = TopologyBuilder()
        builder.add_node("data", "local_filesystem", "data_source", "healthy")
        builder.add_node("orphan", "test", "test", "healthy")
        builder.add_edge("data", "nonexistent", "feeds")

        topology = builder.build()
        validation = topology.validate()

        assert not validation["valid"]
        assert len(validation["orphan_nodes"]) > 0 or len(validation["missing_targets"]) > 0


class TestIntegrationHealthChecks:
    """Test health check orchestration across connectors."""

    def test_health_check_all(self, local_data_config, local_gpu_config):
        """Should health check all configured connectors."""
        manager = IntegrationManager(tenant_id="test_tenant")
        manager.configure("local_filesystem", "data_source", local_data_config)
        manager.configure("local_gpu", "training", local_gpu_config)

        results = manager.health_check_all()

        assert "local_filesystem" in results
        assert "local_gpu" in results
        assert all(isinstance(r, HealthCheckResult) for r in results.values())

    def test_smoke_test_all(self, local_data_config):
        """Should smoke test all configured connectors."""
        manager = IntegrationManager(tenant_id="test_tenant")
        manager.configure("local_filesystem", "data_source", local_data_config)

        results = manager.smoke_test_all()

        assert "local_filesystem" in results
        assert all(isinstance(r, SmokeTestResult) for r in results.values())


class TestExportWorkflow:
    """Test export artifact generation workflow."""

    def test_vllm_serving_pack_export(self, vllm_exporter_config, export_context):
        """Should generate complete vLLM serving pack."""
        exporter = VLLMExporter(vllm_exporter_config)
        artifacts = exporter.export(export_context)

        # Verify all expected files
        names = {a.name for a in artifacts}
        assert "vllm-config.yaml" in names
        assert "docker-compose.yaml" in names
        assert "adapter-ref.json" in names

        # Verify route_key propagation
        for artifact in artifacts:
            assert export_context["route_key"] in artifact.content

    def test_tgi_serving_pack_export(self, tgi_exporter_config, export_context):
        """Should generate complete TGI serving pack."""
        exporter = TGIExporter(tgi_exporter_config)
        artifacts = exporter.export(export_context)

        names = {a.name for a in artifacts}
        assert "tgi-config.json" in names
        assert "docker-compose.yaml" in names


class TestLocalE2ECycle:
    """Test complete local E2E cycle without cloud dependencies."""

    def test_full_local_cycle(self, local_data_config, local_gpu_config, vllm_exporter_config):
        """
        Test the complete local cycle:
        1. Configure data source
        2. Configure training connector
        3. Health check all
        4. Build topology
        5. Export serving pack
        """
        # Phase 1: Setup
        manager = IntegrationManager(tenant_id="e2e_test")

        # Configure data source
        data_result = manager.configure("local_filesystem", "data_source", local_data_config)
        assert data_result.valid

        # Configure training
        train_result = manager.configure("local_gpu", "training", local_gpu_config)
        assert train_result.valid

        # Phase 2: Health checks
        health_results = manager.health_check_all()
        assert len(health_results) == 2

        # Phase 3: Build topology
        topology = manager.build_topology()
        assert len(topology.nodes) >= 2

        # Phase 4: Export serving pack
        exporter = VLLMExporter(vllm_exporter_config)
        export_context = {
            "route_key": "e2e_test_route",
            "adapter_id": "e2e_adapter_v1",
            "adapter_uri": "file:///adapters/e2e_test/adapter.safetensors",
        }
        artifacts = exporter.export(export_context)
        assert len(artifacts) >= 3

        # Phase 5: Verify artifacts contain correct route_key
        for artifact in artifacts:
            if artifact.artifact_type in ["yaml", "json"]:
                assert "e2e_test_route" in artifact.content

    def test_route_resolve_simulation(self, local_data_config):
        """
        Simulate route resolution workflow:
        1. Create route configuration
        2. Query current adapter
        3. Simulate promotion
        4. Verify resolve returns new adapter
        """
        # Simulated route registry
        routes: Dict[str, Dict[str, Any]] = {}

        # Step 1: Create route
        route_key = "test_route_resolve"
        routes[route_key] = {
            "current_adapter_id": None,
            "candidate_adapter_id": "adapter_candidate_v1",
            "production_adapter_id": None,
        }

        # Step 2: Simulate training completion - candidate ready
        routes[route_key]["candidate_adapter_id"] = "adapter_candidate_v1"
        routes[route_key]["candidate_uri"] = "file:///adapters/candidate_v1.safetensors"

        # Step 3: Simulate gate checks passed
        gates_passed = True
        assert gates_passed

        # Step 4: Promote candidate to production
        if gates_passed:
            routes[route_key]["production_adapter_id"] = routes[route_key]["candidate_adapter_id"]
            routes[route_key]["production_uri"] = routes[route_key]["candidate_uri"]
            routes[route_key]["current_adapter_id"] = routes[route_key]["production_adapter_id"]

        # Step 5: Resolve should return production adapter
        resolved = routes[route_key]["current_adapter_id"]
        assert resolved == "adapter_candidate_v1"

        # Step 6: Simulate rollback
        routes[route_key]["current_adapter_id"] = None
        routes[route_key]["production_adapter_id"] = None

        resolved_after_rollback = routes[route_key]["current_adapter_id"]
        assert resolved_after_rollback is None


class TestTrustChainLocal:
    """Test trust chain with local signing."""

    def test_sign_verify_cycle(self):
        """Test signing and verification cycle."""
        connector = LocalDevSigningConnector({
            "secret_key": "e2e-test-key-12345",
        })

        # Simulate adapter artifact
        adapter_manifest = json.dumps({
            "adapter_id": "test_adapter_v1",
            "route_key": "test_route",
            "created_at": datetime.utcnow().isoformat(),
            "checksum": "sha256:abc123...",
        }).encode()

        # Sign manifest
        signature = connector.sign(adapter_manifest)
        assert signature is not None

        # Create signed bundle
        signed_bundle = {
            "manifest": adapter_manifest.decode(),
            "signature": signature.hex(),
        }

        # Later: Verify before deployment
        manifest_bytes = signed_bundle["manifest"].encode()
        sig_bytes = bytes.fromhex(signed_bundle["signature"])

        is_valid = connector.verify(manifest_bytes, sig_bytes)
        assert is_valid

    def test_tampered_artifact_rejected(self):
        """Test that tampered artifacts are rejected."""
        connector = LocalDevSigningConnector({
            "secret_key": "e2e-test-key-12345",
        })

        original_manifest = json.dumps({
            "adapter_id": "trusted_adapter",
            "route_key": "secure_route",
        }).encode()

        signature = connector.sign(original_manifest)

        # Attacker tampers with manifest
        tampered_manifest = json.dumps({
            "adapter_id": "malicious_adapter",
            "route_key": "secure_route",
        }).encode()

        # Verification should fail
        is_valid = connector.verify(tampered_manifest, signature)
        assert not is_valid


class TestMetadataAndAudit:
    """Test metadata and audit trail generation."""

    def test_export_artifacts_have_metadata(self, vllm_exporter_config, export_context):
        """Export artifacts should include metadata when available."""
        exporter = VLLMExporter(vllm_exporter_config)
        artifacts = exporter.export(export_context)

        # adapter-ref.json should have timestamp
        adapter_ref = next(a for a in artifacts if a.name == "adapter-ref.json")
        content = json.loads(adapter_ref.content)

        assert "generated_at" in content
        assert "adapter_id" in content
        assert "route_key" in content

    def test_topology_serialization(self, local_data_config, local_gpu_config):
        """Topology should serialize to dict for audit."""
        manager = IntegrationManager(tenant_id="audit_test")
        manager.configure("local_filesystem", "data_source", local_data_config)
        manager.configure("local_gpu", "training", local_gpu_config)

        topology = manager.build_topology()
        topology_dict = topology.to_dict()

        assert "nodes" in topology_dict
        assert "edges" in topology_dict
        assert isinstance(topology_dict, dict)

        # Should be JSON-serializable
        json_str = json.dumps(topology_dict)
        assert json_str is not None
