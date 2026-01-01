from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from enum import Enum
import uuid

class UserRole(str, Enum):
    ORG_ADMIN = "org_admin"
    SITE_ADMIN = "site_admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    SERVICE_ACCOUNT = "service_account"

class Tenant(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    plan: str = Field(default="starter")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    users: List["User"] = Relationship(back_populates="tenant")
    fleets: List["Fleet"] = Relationship(back_populates="tenant")

class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole = Field(default=UserRole.OPERATOR) 
    tenant_id: str = Field(foreign_key="tenant.id")
    
    tenant: Tenant = Relationship(back_populates="users")

class Fleet(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    tenant_id: str = Field(foreign_key="tenant.id")
    api_key_hash: str
    is_active: bool = True
    
    tenant: Tenant = Relationship(back_populates="fleets")
    jobs: List["Job"] = Relationship(back_populates="fleet")

class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    fleet_id: str = Field(foreign_key="fleet.id")
    type: str # TRAIN, EVAL, DEPLOY
    status: str = Field(default="pending") # pending, running, completed, failed
    config_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
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
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    success: bool = True
