"""
System Settings Model for TensorGuard Platform.
Provides persistent storage for global platform configuration.
"""

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class SystemSettingBase(SQLModel):
    key: str = Field(index=True, unique=True)
    value: str
    description: Optional[str] = None


class SystemSetting(SystemSettingBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None


class KMSKey(SQLModel, table=True):
    """
    Managed cryptographic key for the TensorGuard KMS.
    Persists key metadata (not the actual key material for security).
    """
    kid: str = Field(primary_key=True)  # Key ID
    region: str = Field(default="global")
    algorithm: str = Field(default="Kyber-768 + Ed25519")
    status: str = Field(default="active")  # active, rotating, revoked
    rotation_ttl_days: int = Field(default=30)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_rotated_at: Optional[datetime] = None
    tenant_id: Optional[str] = Field(default=None, foreign_key="tenant.id")


class KMSRotationLog(SQLModel, table=True):
    """Immutable log of key rotation events."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    kid: str = Field(index=True)
    action: str  # created, rotated, revoked
    reason: Optional[str] = None
    performed_by: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pqc_signature: Optional[str] = None
