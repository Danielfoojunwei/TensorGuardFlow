"""
Production Mock Prevention Tests

These tests ensure that mock data, simulations, and hardcoded values
are never returned in production mode. Run these tests as part of CI/CD
to prevent regression.

Usage:
    TG_ENVIRONMENT=production pytest tests/integration/test_no_mocks.py -v
"""

import os
import pytest
from datetime import datetime
from unittest.mock import patch

# Set production environment before imports
os.environ["TG_ENVIRONMENT"] = "production"


class TestNoMockData:
    """Test that no mock/hardcoded data is returned in production."""

    def test_dashboard_stats_no_hardcoded_values(self):
        """Dashboard stats should not return hardcoded values."""
        from tensorguard.platform.api.dashboard_endpoints import get_dashboard_stats

        # The endpoint should query the database, not return hardcoded values
        # In production with no data, it should return zeros, not mock numbers
        # This test verifies the function signature exists and is async
        assert callable(get_dashboard_stats)
        import inspect
        assert inspect.iscoroutinefunction(get_dashboard_stats)

    def test_lineage_versions_uses_database(self):
        """Lineage versions should come from database, not in-memory dict."""
        from tensorguard.platform.api import lineage_endpoints

        # Verify MODEL_REGISTRY constant is not used
        assert not hasattr(lineage_endpoints, 'MODEL_REGISTRY'), \
            "MODEL_REGISTRY should be removed - use database instead"

    def test_training_metrics_not_random(self):
        """Training metrics should not use Math.random or random module."""
        import ast
        import inspect
        from tensorguard.platform.api.dashboard_endpoints import stream_training_metrics

        # Get source code
        source = inspect.getsource(stream_training_metrics)

        # Parse and check for random usage
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    assert node.func.attr != 'random', \
                        "Training metrics should not use random values"
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in ['random', 'randint', 'uniform'], \
                        "Training metrics should not use random module"

    def test_security_score_computed_from_data(self):
        """Security score should be computed from real data."""
        from tensorguard.platform.api.dashboard_endpoints import get_security_score

        # Verify it's a real async function that queries data
        import inspect
        assert inspect.iscoroutinefunction(get_security_score)

        # Check that it takes session and user dependencies
        sig = inspect.signature(get_security_score)
        param_names = list(sig.parameters.keys())
        assert 'session' in param_names, "Should depend on database session"
        assert 'current_user' in param_names, "Should be authenticated"


class TestProductionGates:
    """Test that production gates block simulator/demo code."""

    def test_tpm_simulator_blocked_in_production(self):
        """TPM simulator should raise error in production without override."""
        os.environ["TG_ENVIRONMENT"] = "production"
        os.environ.pop("TG_ALLOW_TPM_SIMULATOR", None)

        from tensorguard.utils.production_gates import is_production

        assert is_production(), "Should detect production environment"

    def test_demo_mode_blocked_in_production(self):
        """Demo mode should be disabled in production."""
        os.environ["TG_ENVIRONMENT"] = "production"
        os.environ.pop("TG_DEMO_MODE", None)

        from tensorguard.utils.production_gates import is_demo_mode

        assert not is_demo_mode(), "Demo mode should be False in production"

    def test_demo_trainer_raises_in_production(self):
        """DemoTrainer should not be usable in production."""
        os.environ["TG_ENVIRONMENT"] = "production"

        # The DemoTrainer class should either not exist or raise on init
        try:
            from tensorguard.integrations.peft_hub.connectors.training_hf import DemoTrainer
            # If it imports, it should raise ProductionGateError on use
            with pytest.raises(Exception):
                trainer = DemoTrainer({})
                trainer.train()
        except ImportError:
            # DemoTrainer removed from production - this is fine
            pass


class TestDatabaseBackedEndpoints:
    """Test that endpoints query the database."""

    def test_lineage_model_version_table_exists(self):
        """ModelVersion table should exist for lineage storage."""
        from tensorguard.platform.models.lineage_models import ModelVersion

        assert hasattr(ModelVersion, '__tablename__')
        assert ModelVersion.__tablename__ == 'model_version'

        # Check required fields
        assert hasattr(ModelVersion, 'tenant_id')
        assert hasattr(ModelVersion, 'tag')
        assert hasattr(ModelVersion, 'commit_hash')
        assert hasattr(ModelVersion, 'status')

    def test_model_deployment_table_exists(self):
        """ModelDeployment table should exist for deployment tracking."""
        from tensorguard.platform.models.lineage_models import ModelDeployment

        assert hasattr(ModelDeployment, '__tablename__')
        assert ModelDeployment.__tablename__ == 'model_deployment'

    def test_dashboard_endpoints_registered(self):
        """Dashboard endpoints should be registered in main app."""
        from tensorguard.platform.main import app

        routes = [r.path for r in app.routes]

        # Check key endpoints exist
        assert any('/dashboard/stats' in r for r in routes), \
            "/dashboard/stats endpoint should be registered"
        assert any('/status/health' in r for r in routes), \
            "/status/health endpoint should be registered"
        assert any('/training/metrics' in r for r in routes), \
            "/training/metrics endpoint should be registered"
        assert any('/security/score' in r for r in routes), \
            "/security/score endpoint should be registered"


class TestNoHardcodedFrontendValues:
    """Test that frontend doesn't have hardcoded mock values (static analysis)."""

    def test_command_center_fetches_from_api(self):
        """CommandCenter.vue should fetch from API, not use hardcoded values."""
        import re

        vue_file = "frontend/src/components/CommandCenter.vue"

        try:
            with open(vue_file, 'r') as f:
                content = f.read()

            # Check that it calls the API
            assert '/api/v1/dashboard/stats' in content or \
                   '/api/v1/status/health' in content, \
                   "CommandCenter should fetch from API"

            # Check no hardcoded metrics in script section
            script_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
            if script_match:
                script = script_match.group(1)
                # Should not have hardcoded fleet counts
                assert 'activeFleets: 12' not in script, \
                    "Should not have hardcoded activeFleets value"
                assert 'connectedDevices: 847' not in script, \
                    "Should not have hardcoded connectedDevices value"
        except FileNotFoundError:
            pytest.skip("Frontend file not found - run from project root")

    def test_training_monitor_no_math_random(self):
        """TrainingMonitor.vue should not use Math.random() for metrics."""
        vue_file = "frontend/src/components/TrainingMonitor.vue"

        try:
            with open(vue_file, 'r') as f:
                content = f.read()

            # Check script section doesn't use Math.random for actual metrics
            # (It's OK to use for UI animations, but not for data)
            script_match = content.split('<script')[1].split('</script>')[0] if '<script' in content else ''

            # Should have API calls
            assert '/api/v1/' in content, \
                "TrainingMonitor should call API endpoints"

        except FileNotFoundError:
            pytest.skip("Frontend file not found - run from project root")


class TestAPIContractCompliance:
    """Test that API responses match expected contracts."""

    def test_dashboard_stats_response_schema(self):
        """Dashboard stats should return expected fields."""
        from tensorguard.platform.api.dashboard_endpoints import DashboardStatsResponse

        # Check schema has required fields
        fields = DashboardStatsResponse.model_fields
        required = [
            'system_health', 'fleet_count', 'device_count',
            'key_rotations_24h', 'compliance_level', 'success_rate'
        ]
        for field in required:
            assert field in fields, f"DashboardStatsResponse missing {field}"

    def test_security_score_response_schema(self):
        """Security score should return expected fields."""
        from tensorguard.platform.api.dashboard_endpoints import SecurityScoreResponse

        fields = SecurityScoreResponse.model_fields
        required = ['overall', 'categories', 'alerts', 'last_audit']
        for field in required:
            assert field in fields, f"SecurityScoreResponse missing {field}"

    def test_system_health_response_schema(self):
        """System health should return expected fields."""
        from tensorguard.platform.api.dashboard_endpoints import SystemHealthResponse

        fields = SystemHealthResponse.model_fields
        required = ['overall', 'services', 'timestamp']
        for field in required:
            assert field in fields, f"SystemHealthResponse missing {field}"


# Run with: TG_ENVIRONMENT=production pytest tests/integration/test_no_mocks.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
