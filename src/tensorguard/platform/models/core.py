from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index, UniqueConstraint
from datetime import datetime
from enum import Enum
import uuid


class UserRole(str, Enum):
    """Legacy user roles - kept for backward compatibility."""
    ORG_ADMIN = "org_admin"
    SITE_ADMIN = "site_admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    SERVICE_ACCOUNT = "service_account"


class OrganizationRole(str, Enum):
    """
    Organization membership roles with clear hierarchy.

    Role Hierarchy (higher can do everything lower can):
        OWNER > ADMIN > OPERATOR > READONLY

    Permissions:
        OWNER: Full control, can delete org, manage billing, transfer ownership
        ADMIN: Manage users, fleets, rotate keys, view audit logs
        OPERATOR: Create/manage fleets, view telemetry, deploy packages
        READONLY: View fleets, telemetry, packages (no modifications)
    """
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    READONLY = "readonly"

    @classmethod
    def hierarchy_level(cls, role: "OrganizationRole") -> int:
        """Return numeric level for role comparison. Higher = more privileged."""
        levels = {
            cls.READONLY: 1,
            cls.OPERATOR: 2,
            cls.ADMIN: 3,
            cls.OWNER: 4,
        }
        return levels.get(role, 0)

    def has_privilege(self, required: "OrganizationRole") -> bool:
        """Check if this role meets or exceeds the required role level."""
        return OrganizationRole.hierarchy_level(self) >= OrganizationRole.hierarchy_level(required)


class JobType(str, Enum):
    """Canonical job types for type safety."""
    TRAIN = "TRAIN"
    EVAL = "EVAL"
    DEPLOY = "DEPLOY"
    VLA_TRAIN = "VLA_TRAIN"
    VLA_EVAL = "VLA_EVAL"


class JobStatus(str, Enum):
    """Canonical job statuses for type safety."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Tenant(SQLModel, table=True):
    """
    Organization/Tenant model - the primary multi-tenancy boundary.

    All resources (fleets, telemetry, packages) are scoped to a tenant.
    Users access tenants through OrganizationMembership with specific roles.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True, unique=True)  # Tenant names must be unique
    plan: str = Field(default="starter")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Settings for organization-wide policies
    settings_json: str = Field(default="{}")  # JSON blob for org settings

    users: List["User"] = Relationship(back_populates="tenant")
    fleets: List["Fleet"] = Relationship(back_populates="tenant")
    memberships: List["OrganizationMembership"] = Relationship(back_populates="organization")


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True)
    name: Optional[str] = None  # Display name
    hashed_password: str
    role: UserRole = Field(default=UserRole.OPERATOR)  # Legacy field
    tenant_id: str = Field(foreign_key="tenant.id", index=True)  # Primary tenant
    is_active: bool = Field(default=True)  # For account deactivation

    tenant: Tenant = Relationship(back_populates="users")
    memberships: List["OrganizationMembership"] = Relationship(back_populates="user")


class OrganizationMembership(SQLModel, table=True):
    """
    Tracks user membership in organizations with role-based access.

    A user can belong to multiple organizations with different roles in each.
    This enables:
    - Cross-org collaboration (user belongs to multiple orgs)
    - Granular RBAC per organization
    - Invitation/onboarding workflows
    - Audit trail for membership changes
    """
    __tablename__ = "organization_membership"
    __table_args__ = (
        UniqueConstraint('user_id', 'organization_id', name='uq_membership_user_org'),
        Index('ix_membership_org_role', 'organization_id', 'role'),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    organization_id: str = Field(foreign_key="tenant.id", index=True)
    role: OrganizationRole = Field(default=OrganizationRole.READONLY)
    # When the membership was created
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Who invited/added this user (for audit)
    invited_by_user_id: Optional[str] = Field(default=None, foreign_key="user.id")
    # Membership status for invitation flows
    is_accepted: bool = Field(default=True)  # True = active, False = pending invitation

    user: User = Relationship(
        back_populates="memberships",
        sa_relationship_kwargs={"foreign_keys": "[OrganizationMembership.user_id]"}
    )
    organization: Tenant = Relationship(back_populates="memberships")


class Fleet(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_fleet_tenant_name'),
        Index('ix_fleet_tenant_active', 'tenant_id', 'is_active'),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    api_key_hash: str
    # Encrypted raw API key for HMAC verification (Fernet encrypted with TG_SECRET_KEY)
    api_key_encrypted: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)
    region: Optional[str] = Field(default=None, index=True)  # For regional queries

    tenant: Tenant = Relationship(back_populates="fleets")
    jobs: List["Job"] = Relationship(back_populates="fleet")


class Job(SQLModel, table=True):
    __table_args__ = (
        Index('ix_job_fleet_status', 'fleet_id', 'status'),
        Index('ix_job_status_created', 'status', 'created_at'),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    fleet_id: str = Field(foreign_key="fleet.id", index=True)
    type: str = Field(index=True)  # Uses JobType values
    status: str = Field(default=JobStatus.PENDING.value, index=True)
    config_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    completed_at: Optional[datetime] = None

    fleet: Fleet = Relationship(back_populates="jobs")

class AuditLog(SQLModel, table=True):
    """Traceability ledger for SOC 2 and ISO 9001 compliance."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    user_id: Optional[str] = Field(foreign_key="user.id", nullable=True)
    action: str  # e.g., "KEY_SIGN", "PACKAGE_UPLOAD", "MODEL_DEPLOY"
    resource_id: str
    resource_type: str
    details: str = Field(default="{}") # JSON blob
    pqc_signature: Optional[str] = None # Dilithium-3 hex signature
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    success: bool = True

class ReplayNonce(SQLModel, table=True):
    """Store nonces to prevent HMAC replay attacks."""
    nonce: str = Field(primary_key=True)
    fleet_id: str = Field(index=True)
    timestamp: int = Field(index=True)
    expires_at: datetime = Field(index=True)
