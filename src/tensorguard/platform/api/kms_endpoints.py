"""
KMS (Key Management Service) API Endpoints.
Provides engineer control over key rotation and attestation policies.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import secrets
import json

from ..database import get_session
from ..models.settings_models import SystemSetting
from ..models.core import User, AuditLog
from ..auth import get_current_user
from ...crypto.sig import generate_hybrid_sig_keypair, sign_hybrid

router = APIRouter()


class KeyInfo(BaseModel):
    kid: str
    region: str
    created_at: str
    rotation_ttl: str
    status: str
    algorithm: str


class RotationRequest(BaseModel):
    kid: str
    reason: Optional[str] = "manual_rotation"


# In-memory key store for MVP (production would use HSM/CloudKMS)
KEY_STORE = {
    "key-us-east-1": {
        "kid": "key-us-east-1",
        "region": "us-east-1",
        "created_at": "2025-12-01T00:00:00Z",
        "rotation_ttl": "30d",
        "status": "active",
        "algorithm": "Kyber-768 + Ed25519"
    },
    "key-eu-central": {
        "kid": "key-eu-central",
        "region": "eu-central-1",
        "created_at": "2026-01-08T00:00:00Z",
        "rotation_ttl": "30d",
        "status": "active",
        "algorithm": "Kyber-768 + Ed25519"
    },
    "fleet-master": {
        "kid": "fleet-master",
        "region": "global",
        "created_at": "2026-01-01T00:00:00Z",
        "rotation_ttl": "90d",
        "status": "active",
        "algorithm": "Dilithium-3"
    }
}


@router.get("/kms/keys")
async def list_keys(session: Session = Depends(get_session)):
    """List all managed keys with their lifecycle status."""
    keys = []
    for kid, info in KEY_STORE.items():
        created = datetime.fromisoformat(info["created_at"].replace("Z", "+00:00"))
        ttl_days = int(info["rotation_ttl"].replace("d", ""))
        expires = created + timedelta(days=ttl_days)
        days_remaining = (expires - datetime.now(created.tzinfo)).days
        
        keys.append({
            **info,
            "days_remaining": max(0, days_remaining),
            "expires_at": expires.isoformat()
        })
    
    return {"keys": keys}


@router.get("/kms/keys/{kid}")
async def get_key(kid: str, session: Session = Depends(get_session)):
    """Get detailed info about a specific key."""
    if kid not in KEY_STORE:
        raise HTTPException(status_code=404, detail=f"Key {kid} not found")
    
    info = KEY_STORE[kid]
    created = datetime.fromisoformat(info["created_at"].replace("Z", "+00:00"))
    ttl_days = int(info["rotation_ttl"].replace("d", ""))
    expires = created + timedelta(days=ttl_days)
    
    return {
        **info,
        "days_remaining": max(0, (expires - datetime.now(created.tzinfo)).days),
        "expires_at": expires.isoformat(),
        "rotation_history": [
            {"timestamp": created.isoformat(), "action": "created", "by": "system"},
        ]
    }


@router.post("/kms/rotate")
async def rotate_key(
    req: RotationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger a key rotation.
    Creates an immutable audit log entry with PQC signature.
    """
    if req.kid not in KEY_STORE:
        raise HTTPException(status_code=404, detail=f"Key {req.kid} not found")
    
    # Update key in store
    old_created = KEY_STORE[req.kid]["created_at"]
    KEY_STORE[req.kid]["created_at"] = datetime.utcnow().isoformat() + "Z"
    KEY_STORE[req.kid]["status"] = "active"
    
    # Create PQC-signed audit log
    pub, priv = generate_hybrid_sig_keypair()
    log_entry = {
        "action": "KEY_ROTATION",
        "kid": req.kid,
        "reason": req.reason,
        "old_created": old_created,
        "new_created": KEY_STORE[req.kid]["created_at"],
        "timestamp": datetime.utcnow().isoformat()
    }
    sig = sign_hybrid(priv, json.dumps(log_entry).encode())
    
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="KEY_ROTATION",
        resource_id=req.kid,
        resource_type="kms_key",
        details=json.dumps(log_entry),
        pqc_signature=sig["sig_pqc"]
    )
    session.add(audit)
    session.commit()
    
    return {
        "status": "rotated",
        "kid": req.kid,
        "new_created_at": KEY_STORE[req.kid]["created_at"],
        "audit_id": audit.id
    }


@router.get("/kms/attestation-policies")
async def get_attestation_policies(session: Session = Depends(get_session)):
    """Get TEE attestation policy configuration."""
    # Load from settings or use defaults
    attestation_level = "4"
    setting = session.exec(
        select(SystemSetting).where(SystemSetting.key == "attestation_level")
    ).first()
    if setting:
        attestation_level = setting.value
    
    return {
        "current_level": int(attestation_level),
        "levels": [
            {"level": 1, "name": "Software Only", "description": "No hardware attestation required"},
            {"level": 2, "name": "TPM 2.0", "description": "TPM-backed software claims"},
            {"level": 3, "name": "TEE Soft", "description": "Software-based enclave attestation"},
            {"level": 4, "name": "TEE Hard", "description": "Hardware-backed enclave with evidence fabric"}
        ]
    }


@router.get("/kms/rotation-schedule")
async def get_rotation_schedule(session: Session = Depends(get_session)):
    """Get the upcoming key rotation schedule."""
    schedule = []
    for kid, info in KEY_STORE.items():
        created = datetime.fromisoformat(info["created_at"].replace("Z", "+00:00"))
        ttl_days = int(info["rotation_ttl"].replace("d", ""))
        expires = created + timedelta(days=ttl_days)
        
        schedule.append({
            "kid": kid,
            "algorithm": info["algorithm"],
            "next_rotation": expires.isoformat(),
            "days_remaining": max(0, (expires - datetime.now(created.tzinfo)).days),
            "auto_rotate": True
        })
    
    # Sort by days remaining
    schedule.sort(key=lambda x: x["days_remaining"])
    return {"schedule": schedule}
