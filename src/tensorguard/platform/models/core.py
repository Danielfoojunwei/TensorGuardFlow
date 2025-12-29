from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
import uuid

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
    role: str = Field(default="operator") # owner, admin, operator, auditor
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
