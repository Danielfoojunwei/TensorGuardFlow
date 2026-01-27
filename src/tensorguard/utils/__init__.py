"""
TensorGuard Utilities Module

Provides centralized access to common utilities.

Note: Some modules have side effects at import time:
- config: Creates settings singleton with production validation
- logging: Creates global logger that imports config

Import these directly when needed:
- from tensorguard.utils.config import settings
- from tensorguard.utils.logging import get_logger
"""

# Production gates and environment checks
from .production_gates import (
    ProductionGateError,
    is_production,
    is_demo_mode,
    require_env,
    require_dependency,
    require_file,
    require_directory,
    block_demo_mode,
    assert_production_invariants,
)

# Feature flags
from .feature_flags import FeatureFlags, FeatureFlagCategory, is_flag_enabled

# Exception hierarchy
from .exceptions import (
    TensorGuardError,
    CryptographyError,
    KeyManagementError,
    ConfigurationError,
    CommunicationError,
    ValidationError,
    ContractError,
    PipelineError,
    PolicyError,
    IdentityError,
    EvidenceError,
)

# Serialization
from .serialization import safe_dumps, safe_loads, safe_dump, safe_load

# HTTP client
from .http import StandardClient, get_standard_client

# File operations
from .files import atomic_write, sanitize_path

__all__ = [
    # Production gates
    "ProductionGateError",
    "is_production",
    "is_demo_mode",
    "require_env",
    "require_dependency",
    "require_file",
    "require_directory",
    "block_demo_mode",
    "assert_production_invariants",
    # Feature flags
    "FeatureFlags",
    "FeatureFlagCategory",
    "is_flag_enabled",
    # Exceptions
    "TensorGuardError",
    "CryptographyError",
    "KeyManagementError",
    "ConfigurationError",
    "CommunicationError",
    "ValidationError",
    "ContractError",
    "PipelineError",
    "PolicyError",
    "IdentityError",
    "EvidenceError",
    # Serialization
    "safe_dumps",
    "safe_loads",
    "safe_dump",
    "safe_load",
    # HTTP
    "StandardClient",
    "get_standard_client",
    # Files
    "atomic_write",
    "sanitize_path",
]
