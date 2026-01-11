"""
FedMoE Data Models - Experts & Skills Evidence
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON
import uuid

class FedMoEExpert(SQLModel, table=True):
    """Registry of specialized FedMoE experts trained/adapted on edge nodes."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)
    name: str # e.g. "manipulation_grasp_v2"
    base_model: str # e.g. "openvla-7b"
    version: str = Field(default="1.0.0") # Semantic versioning for rollback
    
    status: str = Field(default="adapting") # adapting, validated, deployed, archived
    accuracy_score: Optional[float] = None
    collision_rate: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata for MoE Gating
    gating_config: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    
    # Relationships
    evidences: List["SkillEvidence"] = Relationship(back_populates="expert")

class SkillEvidence(SQLModel, table=True):
    """Tamper-evident proof of skill acquisition or validation for a FedMoE expert."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    expert_id: str = Field(foreign_key="fedmoeexpert.id", index=True)
    
    evidence_type: str # SIM_SUCCESS, REAL_WORLD_VLD, PEER_REVIEW
    value_json: str = Field(default="{}")
    
    # Evidence Fabric metadata
    signed_proof: Optional[str] = None # Dilithium-3 signature of canonical evidence
    manifest_hash: Optional[str] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    expert: FedMoEExpert = Relationship(back_populates="evidences")
