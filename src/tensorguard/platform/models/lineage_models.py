"""
Model Lineage Database Models

Provides database-backed storage for model versions, replacing
the in-memory MODEL_REGISTRY mock data.
"""

from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Index
from datetime import datetime
from enum import Enum
import uuid


class ModelVersionStatus(str, Enum):
    """Status of a model version in the lineage."""
    DRAFT = "draft"
    VERIFIED = "verified"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    ROLLBACK = "rollback"


class ModelVersion(SQLModel, table=True):
    """
    Tracks model versions for lineage and deployment history.

    This replaces the in-memory MODEL_REGISTRY with real database storage.
    """
    __tablename__ = "model_version"
    __table_args__ = (
        Index('ix_model_version_tenant_tag_composite', 'tenant_id', 'tag'),
        Index('ix_model_version_tenant_status_composite', 'tenant_id', 'status'),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)

    # Version identification
    tag: str = Field(index=True)  # e.g., "v2.1.0"
    commit_hash: str  # Short hash for display
    message: str  # Commit/version message
    author: str  # Who created this version

    # Status tracking
    status: str = Field(default=ModelVersionStatus.DRAFT.value, index=True)

    # Quality metrics
    test_pass_rate: Optional[str] = Field(default=None)  # e.g., "98/98"
    accuracy: Optional[float] = Field(default=None)

    # Model metadata
    base_model: Optional[str] = Field(default=None)  # e.g., "openvla-7b"
    peft_method: Optional[str] = Field(default=None)  # e.g., "lora"
    architecture_json: Optional[str] = Field(default=None)  # JSON blob
    metrics_json: Optional[str] = Field(default=None)  # JSON blob

    # Artifact references
    artifact_uri: Optional[str] = Field(default=None)  # S3/GCS/Azure path
    hf_hub_id: Optional[str] = Field(default=None)  # HuggingFace Hub ID

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    deployed_at: Optional[datetime] = Field(default=None)
    archived_at: Optional[datetime] = Field(default=None)


class ModelDeployment(SQLModel, table=True):
    """
    Tracks deployment history for model versions.

    Provides audit trail of all deployments and rollbacks.
    """
    __tablename__ = "model_deployment"
    __table_args__ = (
        Index('ix_model_deployment_tenant', 'tenant_id', 'created_at'),
        Index('ix_model_deployment_fleet', 'fleet_id', 'created_at'),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)
    fleet_id: Optional[str] = Field(default=None, index=True)  # Target fleet (None = all)

    # Version info
    version_id: str = Field(index=True)  # FK to ModelVersion
    previous_version_id: Optional[str] = Field(default=None)

    # Deployment details
    reason: str = Field(default="manual_deployment")
    deployed_by: str  # User ID

    # Rollout status
    rollout_percentage: int = Field(default=100)
    is_active: bool = Field(default=True)

    # Audit
    pqc_signature: Optional[str] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    completed_at: Optional[datetime] = Field(default=None)
