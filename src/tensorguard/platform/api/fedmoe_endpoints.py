from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Any, Dict, Optional
from datetime import datetime
import secrets
import json

from ..database import get_session
from ..models.core import User, AuditLog
from ..models.fedmoe_models import FedMoEExpert, SkillEvidence
from ..auth import get_current_user
from ...crypto.sig import generate_hybrid_sig_keypair, sign_hybrid
from ...evidence.canonical import canonical_bytes

from pydantic import BaseModel

router = APIRouter()

class ExpertCreate(BaseModel):
    name: str
    base_model: str

@router.get("/experts", response_model=List[FedMoEExpert])
async def list_experts(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """List all experts for the tenant."""
    experts = session.exec(select(FedMoEExpert).where(FedMoEExpert.tenant_id == current_user.tenant_id)).all()
    return list(experts) if experts else []

@router.post("/experts", response_model=FedMoEExpert)
async def create_expert(req: ExpertCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Create a new FedMoE expert and log the event."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Expert name cannot be empty")
    
    import re
    # Extreme sanitization for enterprise safety
    sanitized_name = re.sub(r'[^a-zA-Z0-9_\-\s]', '', req.name)[:50]
    
    expert = FedMoEExpert(
        name=sanitized_name,
        base_model=req.base_model,
        tenant_id=current_user.tenant_id,
        status="adapting"
    )
    session.add(expert)
    session.commit()
    session.refresh(expert)
    
    # Log the creation in AuditLog with PQC signature
    # (In real world, we'd use a persistent platform key)
    pub, priv = generate_hybrid_sig_keypair()
    log_entry = {
        "action": "EXPERT_CREATED",
        "expert_id": expert.id,
        "name": expert.name,
        "timestamp": datetime.utcnow().isoformat()
    }
    sig = sign_hybrid(priv, json.dumps(log_entry).encode())
    
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="EXPERT_CREATED",
        resource_id=expert.id,
        resource_type="fedmoe_expert",
        details=json.dumps(log_entry),
        pqc_signature=sig["sig_pqc"]
    )
    session.add(audit)
    session.commit()
    
    return expert

@router.get("/skills-library", response_model=List[Dict[str, Any]])
async def get_skills_library(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Fetch the validated skills library (experts with at least one evidence)."""
    experts = session.exec(select(FedMoEExpert).where(
        FedMoEExpert.tenant_id == current_user.tenant_id,
        FedMoEExpert.status == "validated"
    )).all()
    
    library = []
    for e in experts:
        library.append({
            "id": e.id,
            "name": e.name,
            "base_model": e.base_model,
            "accuracy": e.accuracy_score,
            "collision_rate": e.collision_rate,
            "evidence_count": len(e.evidences),
            "last_validated": e.updated_at.isoformat()
        })
    return library

@router.post("/experts/{expert_id}/evidence", response_model=SkillEvidence)
async def add_evidence(expert_id: str, evidence_type: str, value: Dict[str, Any], session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Add evidence of a skill to an expert."""
    expert = session.get(FedMoEExpert, expert_id)
    if not expert or expert.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Expert not found")
        
    evidence = SkillEvidence(
        expert_id=expert_id,
        evidence_type=evidence_type,
        value_json=json.dumps(value)
    )
    
    # Proof of work signing
    pub, priv = generate_hybrid_sig_keypair()
    proof_data = {"type": evidence_type, "value": value}
    sig = sign_hybrid(priv, json.dumps(proof_data).encode())
    
    evidence.signed_proof = sig["sig_pqc"]
    
    session.add(evidence)
    
    # Auto-update expert status if evidence is significant
    if evidence_type == "SIM_SUCCESS" and value.get("score", 0) > 0.8:
        expert.status = "validated"
        expert.accuracy_score = value.get("score")
        expert.collision_rate = value.get("collision_rate", 0.05)
        expert.updated_at = datetime.utcnow()
        session.add(expert)
        
    session.commit()
    session.refresh(evidence)
    return evidence
