"""
TensorGuard Identity Module

Machine Identity Guard - Certificate Lifecycle Management for Zero-Trust Robotics.

Provides:
- Certificate inventory and discovery
- Policy-driven automated renewal
- ACME integration (Let's Encrypt, ZeroSSL)
- Private CA for mTLS/client auth
- Tamper-evident audit logging
"""

__version__ = "1.0.0"

# Core services
from .policy_engine import PolicyEngine
from .inventory import InventoryService
from .audit import AuditService
from .scheduler import RenewalScheduler

# ACME
from .acme.client import ACMEClient

# Private CA
from .ca.private_ca import PrivateCAClient

# Keys
from .keys.provider import KeyProvider, FileKeyProvider

__all__ = [
    "PolicyEngine",
    "InventoryService", 
    "AuditService",
    "RenewalScheduler",
    "ACMEClient",
    "PrivateCAClient",
    "KeyProvider",
    "FileKeyProvider",
]
