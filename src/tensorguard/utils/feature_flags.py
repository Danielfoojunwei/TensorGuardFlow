"""
Feature Flags System

Centralized feature flag management for TensorGuard platform.
Supports environment-based configuration with type-safe access.

Usage:
    from tensorguard.utils.feature_flags import FeatureFlags

    if FeatureFlags.is_enabled("identity_renewal"):
        # Run identity renewal logic
        pass
"""

import os
import logging
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

logger = logging.getLogger(__name__)


class FeatureFlagCategory(str, Enum):
    """Categories for feature flags."""
    WORKER = "worker"
    IDENTITY = "identity"
    TRAINING = "training"
    SECURITY = "security"
    EXPERIMENTAL = "experimental"


@dataclass
class FeatureFlagDef:
    """Definition of a feature flag."""
    name: str
    env_var: str
    default: bool
    description: str
    category: FeatureFlagCategory
    dependencies: list = field(default_factory=list)

    def is_enabled(self) -> bool:
        """Check if this flag is enabled via environment."""
        value = os.getenv(self.env_var, str(self.default)).lower()
        return value in ("true", "1", "yes", "on")


# Registry of all feature flags
_FLAG_REGISTRY: Dict[str, FeatureFlagDef] = {}


def _register_flag(flag: FeatureFlagDef) -> FeatureFlagDef:
    """Register a feature flag."""
    _FLAG_REGISTRY[flag.name] = flag
    return flag


# Worker flags
WORKER_IDENTITY_RENEWAL = _register_flag(FeatureFlagDef(
    name="worker_identity_renewal",
    env_var="TG_WORKER_IDENTITY_RENEWAL",
    default=True,
    description="Enable identity certificate renewal worker",
    category=FeatureFlagCategory.WORKER,
))

WORKER_TELEMETRY_AGGREGATION = _register_flag(FeatureFlagDef(
    name="worker_telemetry_aggregation",
    env_var="TG_WORKER_TELEMETRY_AGGREGATION",
    default=True,
    description="Enable telemetry aggregation worker",
    category=FeatureFlagCategory.WORKER,
))

WORKER_JOB_CLEANUP = _register_flag(FeatureFlagDef(
    name="worker_job_cleanup",
    env_var="TG_WORKER_JOB_CLEANUP",
    default=True,
    description="Enable stale job cleanup worker",
    category=FeatureFlagCategory.WORKER,
))

# Identity flags
IDENTITY_ACME_ENABLED = _register_flag(FeatureFlagDef(
    name="identity_acme_enabled",
    env_var="TG_IDENTITY_ACME_ENABLED",
    default=False,
    description="Enable ACME certificate issuance (requires ACME provider config)",
    category=FeatureFlagCategory.IDENTITY,
    dependencies=["josepy", "cryptography"],
))

IDENTITY_PRIVATE_CA = _register_flag(FeatureFlagDef(
    name="identity_private_ca",
    env_var="TG_IDENTITY_PRIVATE_CA",
    default=True,
    description="Enable private CA certificate issuance",
    category=FeatureFlagCategory.IDENTITY,
))

# Training flags
TRAINING_FEDERATED = _register_flag(FeatureFlagDef(
    name="training_federated",
    env_var="TG_TRAINING_FEDERATED",
    default=False,
    description="Enable federated training (requires Flower)",
    category=FeatureFlagCategory.TRAINING,
    dependencies=["flwr"],
))

TRAINING_DP_ENABLED = _register_flag(FeatureFlagDef(
    name="training_dp_enabled",
    env_var="TG_TRAINING_DP_ENABLED",
    default=True,
    description="Enable differential privacy in training",
    category=FeatureFlagCategory.TRAINING,
))

# Security flags
SECURITY_PQC_ENABLED = _register_flag(FeatureFlagDef(
    name="security_pqc_enabled",
    env_var="TG_SECURITY_PQC_ENABLED",
    default=False,
    description="Enable post-quantum cryptography (requires liboqs)",
    category=FeatureFlagCategory.SECURITY,
    dependencies=["liboqs"],
))

SECURITY_HMAC_REPLAY_PROTECTION = _register_flag(FeatureFlagDef(
    name="security_hmac_replay_protection",
    env_var="TG_SECURITY_HMAC_REPLAY",
    default=True,
    description="Enable HMAC replay attack protection",
    category=FeatureFlagCategory.SECURITY,
))


class FeatureFlags:
    """
    Static interface for checking feature flags.

    All methods are class methods for easy access without instantiation.
    """

    @classmethod
    def is_enabled(cls, flag_name: str) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            flag_name: Name of the feature flag

        Returns:
            True if enabled, False otherwise

        Raises:
            KeyError: If flag_name is not registered
        """
        if flag_name not in _FLAG_REGISTRY:
            logger.warning(f"Unknown feature flag: {flag_name}")
            return False
        return _FLAG_REGISTRY[flag_name].is_enabled()

    @classmethod
    def get_flag(cls, flag_name: str) -> Optional[FeatureFlagDef]:
        """Get flag definition by name."""
        return _FLAG_REGISTRY.get(flag_name)

    @classmethod
    def list_flags(cls, category: Optional[FeatureFlagCategory] = None) -> Dict[str, bool]:
        """
        List all flags and their current status.

        Args:
            category: Optional category filter

        Returns:
            Dict mapping flag names to enabled status
        """
        result = {}
        for name, flag in _FLAG_REGISTRY.items():
            if category is None or flag.category == category:
                result[name] = flag.is_enabled()
        return result

    @classmethod
    def get_enabled_flags(cls) -> Set[str]:
        """Get set of all enabled flag names."""
        return {name for name, flag in _FLAG_REGISTRY.items() if flag.is_enabled()}

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        """
        Get comprehensive summary of all feature flags.

        Returns:
            Dict with flag status organized by category
        """
        by_category: Dict[str, Dict[str, bool]] = {}
        for name, flag in _FLAG_REGISTRY.items():
            cat_name = flag.category.value
            if cat_name not in by_category:
                by_category[cat_name] = {}
            by_category[cat_name][name] = flag.is_enabled()

        return {
            "total_flags": len(_FLAG_REGISTRY),
            "enabled_count": len(cls.get_enabled_flags()),
            "by_category": by_category,
        }

    @classmethod
    def check_dependencies(cls, flag_name: str) -> Dict[str, bool]:
        """
        Check if dependencies for a flag are available.

        Args:
            flag_name: Name of the feature flag

        Returns:
            Dict mapping dependency names to availability status
        """
        flag = _FLAG_REGISTRY.get(flag_name)
        if not flag:
            return {}

        result = {}
        for dep in flag.dependencies:
            try:
                __import__(dep)
                result[dep] = True
            except ImportError:
                result[dep] = False
        return result


# Convenience functions for direct access
def is_flag_enabled(flag_name: str) -> bool:
    """Check if a feature flag is enabled."""
    return FeatureFlags.is_enabled(flag_name)


def worker_identity_renewal_enabled() -> bool:
    """Check if worker identity renewal is enabled."""
    return WORKER_IDENTITY_RENEWAL.is_enabled()


def worker_telemetry_aggregation_enabled() -> bool:
    """Check if worker telemetry aggregation is enabled."""
    return WORKER_TELEMETRY_AGGREGATION.is_enabled()


def worker_job_cleanup_enabled() -> bool:
    """Check if worker job cleanup is enabled."""
    return WORKER_JOB_CLEANUP.is_enabled()
