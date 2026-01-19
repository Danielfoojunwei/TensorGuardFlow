"""
Feature Flags Unit Tests

Tests for the feature flag system including:
- Flag registration and lookup
- Environment-based configuration
- Category filtering
- Dependency checking

Run with: pytest tests/unit/test_feature_flags.py -v
"""

import os
import pytest
from unittest.mock import patch


class TestFeatureFlagBasics:
    """Test basic feature flag functionality."""

    def test_flag_registry_populated(self):
        """Flag registry should have registered flags."""
        from tensorguard.utils.feature_flags import _FLAG_REGISTRY

        assert len(_FLAG_REGISTRY) > 0
        assert "worker_identity_renewal" in _FLAG_REGISTRY
        assert "worker_telemetry_aggregation" in _FLAG_REGISTRY
        assert "worker_job_cleanup" in _FLAG_REGISTRY

    def test_feature_flags_is_enabled(self):
        """FeatureFlags.is_enabled should check flag status."""
        from tensorguard.utils.feature_flags import FeatureFlags

        # Worker flags are enabled by default
        assert FeatureFlags.is_enabled("worker_identity_renewal") is True
        assert FeatureFlags.is_enabled("worker_job_cleanup") is True

        # Unknown flags should return False
        assert FeatureFlags.is_enabled("nonexistent_flag") is False

    def test_feature_flags_list_flags(self):
        """FeatureFlags.list_flags should return all flags."""
        from tensorguard.utils.feature_flags import FeatureFlags, FeatureFlagCategory

        all_flags = FeatureFlags.list_flags()
        assert isinstance(all_flags, dict)
        assert len(all_flags) > 0

        # Filter by category
        worker_flags = FeatureFlags.list_flags(category=FeatureFlagCategory.WORKER)
        assert "worker_identity_renewal" in worker_flags
        assert "worker_telemetry_aggregation" in worker_flags

    def test_feature_flags_summary(self):
        """FeatureFlags.summary should return comprehensive status."""
        from tensorguard.utils.feature_flags import FeatureFlags

        summary = FeatureFlags.summary()
        assert "total_flags" in summary
        assert "enabled_count" in summary
        assert "by_category" in summary
        assert summary["total_flags"] > 0

    def test_get_enabled_flags(self):
        """get_enabled_flags should return set of enabled flag names."""
        from tensorguard.utils.feature_flags import FeatureFlags

        enabled = FeatureFlags.get_enabled_flags()
        assert isinstance(enabled, set)
        # Worker flags are enabled by default
        assert "worker_identity_renewal" in enabled


class TestFeatureFlagEnvironment:
    """Test environment-based flag configuration."""

    def test_flag_respects_environment(self):
        """Flags should respect environment variable settings."""
        from tensorguard.utils.feature_flags import FeatureFlags

        # Test with environment override
        with patch.dict(os.environ, {"TG_WORKER_IDENTITY_RENEWAL": "false"}):
            # Need to reimport to get fresh evaluation
            from tensorguard.utils import feature_flags
            from importlib import reload
            reload(feature_flags)

            assert feature_flags.worker_identity_renewal_enabled() is False

        # Restore default behavior
        with patch.dict(os.environ, {"TG_WORKER_IDENTITY_RENEWAL": "true"}):
            from tensorguard.utils import feature_flags
            from importlib import reload
            reload(feature_flags)

    def test_flag_various_true_values(self):
        """Flags should recognize various true values."""
        from tensorguard.utils.feature_flags import FeatureFlagDef, FeatureFlagCategory

        flag = FeatureFlagDef(
            name="test_flag",
            env_var="TEST_FLAG_VAR",
            default=False,
            description="Test flag",
            category=FeatureFlagCategory.EXPERIMENTAL,
        )

        for value in ["true", "TRUE", "True", "1", "yes", "YES", "on", "ON"]:
            with patch.dict(os.environ, {"TEST_FLAG_VAR": value}):
                assert flag.is_enabled() is True, f"Failed for value: {value}"

    def test_flag_various_false_values(self):
        """Flags should recognize various false values."""
        from tensorguard.utils.feature_flags import FeatureFlagDef, FeatureFlagCategory

        flag = FeatureFlagDef(
            name="test_flag",
            env_var="TEST_FLAG_VAR",
            default=True,
            description="Test flag",
            category=FeatureFlagCategory.EXPERIMENTAL,
        )

        for value in ["false", "FALSE", "False", "0", "no", "NO", "off", "OFF", ""]:
            with patch.dict(os.environ, {"TEST_FLAG_VAR": value}):
                assert flag.is_enabled() is False, f"Failed for value: {value}"


class TestFeatureFlagDependencies:
    """Test feature flag dependency checking."""

    def test_check_dependencies_returns_availability(self):
        """check_dependencies should return dependency availability status."""
        from tensorguard.utils.feature_flags import FeatureFlags

        # Worker flags have no dependencies
        deps = FeatureFlags.check_dependencies("worker_identity_renewal")
        assert deps == {}

        # Security PQC flag has liboqs dependency
        deps = FeatureFlags.check_dependencies("security_pqc_enabled")
        assert "liboqs" in deps
        # liboqs is probably not installed in test environment
        assert deps["liboqs"] is False

    def test_check_dependencies_unknown_flag(self):
        """check_dependencies should return empty for unknown flags."""
        from tensorguard.utils.feature_flags import FeatureFlags

        deps = FeatureFlags.check_dependencies("nonexistent_flag")
        assert deps == {}


class TestWorkerConvenienceFunctions:
    """Test convenience functions for worker flags."""

    def test_worker_identity_renewal_enabled(self):
        """worker_identity_renewal_enabled should return boolean."""
        from tensorguard.utils.feature_flags import worker_identity_renewal_enabled

        result = worker_identity_renewal_enabled()
        assert isinstance(result, bool)

    def test_worker_telemetry_aggregation_enabled(self):
        """worker_telemetry_aggregation_enabled should return boolean."""
        from tensorguard.utils.feature_flags import worker_telemetry_aggregation_enabled

        result = worker_telemetry_aggregation_enabled()
        assert isinstance(result, bool)

    def test_worker_job_cleanup_enabled(self):
        """worker_job_cleanup_enabled should return boolean."""
        from tensorguard.utils.feature_flags import worker_job_cleanup_enabled

        result = worker_job_cleanup_enabled()
        assert isinstance(result, bool)

    def test_is_flag_enabled_function(self):
        """is_flag_enabled function should work correctly."""
        from tensorguard.utils.feature_flags import is_flag_enabled

        # Known flag
        assert isinstance(is_flag_enabled("worker_identity_renewal"), bool)

        # Unknown flag
        assert is_flag_enabled("nonexistent") is False
