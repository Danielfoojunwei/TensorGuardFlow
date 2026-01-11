"""
System Settings Model for TensorGuard Platform.
Provides persistent storage for global platform configuration.
"""

from sqlmodel import SQLModel, Field
from sqlalchemy import Index
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class KeyStatus(str, Enum):
    """Canonical KMS key lifecycle states."""
    ACTIVE = "active"
    ROTATING = "rotating"
    REVOKED = "revoked"
    EXPIRED = "expired"


class RotationAction(str, Enum):
    """Canonical key rotation actions."""
    CREATED = "created"
    ROTATED = "rotated"
    REVOKED = "revoked"
    EXPIRED = "expired"


class SystemSettingBase(SQLModel):
    key: str = Field(index=True, unique=True)
    value: str
    description: Optional[str] = None


class SystemSetting(SystemSettingBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None
    tenant_id: Optional[str] = Field(default=None, foreign_key="tenant.id", index=True)


class KMSKey(SQLModel, table=True):
    """
    Managed cryptographic key for the TensorGuard KMS.
    Persists key metadata (not the actual key material for security).
    """
    __table_args__ = (
        Index('ix_kms_tenant_status', 'tenant_id', 'status'),
        Index('ix_kms_rotation_due', 'status', 'last_rotated_at'),
    )

    kid: str = Field(primary_key=True)  # Key ID
    region: str = Field(default="global", index=True)
    algorithm: str = Field(default="Kyber-768 + Ed25519")
    status: str = Field(default=KeyStatus.ACTIVE.value, index=True)
    rotation_ttl_days: int = Field(default=30)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_rotated_at: Optional[datetime] = None
    next_rotation_at: Optional[datetime] = None  # Pre-computed rotation deadline
    tenant_id: Optional[str] = Field(default=None, foreign_key="tenant.id", index=True)

    # Key usage tracking
    usage_count: int = Field(default=0)
    last_used_at: Optional[datetime] = None


class KMSRotationLog(SQLModel, table=True):
    """Immutable log of key rotation events."""
    __table_args__ = (
        Index('ix_rotation_kid_timestamp', 'kid', 'timestamp'),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    kid: str = Field(index=True, foreign_key="kmskey.kid")  # Foreign key to KMSKey
    action: str = Field(index=True)  # Uses RotationAction values
    reason: Optional[str] = None
    performed_by: Optional[str] = Field(default=None, foreign_key="user.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    pqc_signature: Optional[str] = None  # Dilithium-3 signature for tamper-evidence
