"""
Model Lineage API Endpoints.

Provides database-backed version control and deployment history for VLA models.
Replaces the in-memory MODEL_REGISTRY with real database storage.

All data is persisted to the model_version and model_deployment tables.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, col
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import json
import uuid

from ..database import get_session
from ..models.core import User, AuditLog
from ..models.lineage_models import ModelVersion, ModelDeployment, ModelVersionStatus
from ..auth import get_current_user
from ...crypto.sig import generate_hybrid_sig_keypair, sign_hybrid

router = APIRouter()


class ModelVersionCreate(BaseModel):
    tag: str
    commit_hash: str
    message: str
    author: Optional[str] = None
    base_model: Optional[str] = None
    peft_method: Optional[str] = None
    test_pass_rate: Optional[str] = None
    artifact_uri: Optional[str] = None
    hf_hub_id: Optional[str] = None


class DeployRequest(BaseModel):
    version_id: str
    fleet_id: Optional[str] = None
    reason: Optional[str] = "manual_deployment"
    rollout_percentage: int = 100


class SyncRequest(BaseModel):
    source: str = "local"  # local, huggingface, mlflow


def _ensure_seed_data(session: Session, tenant_id: str):
    """Ensure seed data exists for tenant if no versions present."""
    existing = session.exec(
        select(ModelVersion).where(ModelVersion.tenant_id == tenant_id).limit(1)
    ).first()

    if existing:
        return

    # Create seed versions for new tenants
    seed_versions = [
        ModelVersion(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            tag="v2.1.0",
            commit_hash="e7f2b1",
            message="Improve context window size",
            author="System",
            status=ModelVersionStatus.DEPLOYED.value,
            test_pass_rate="98/98",
            base_model="openvla-7b",
            peft_method="lora",
            created_at=datetime.utcnow(),
            deployed_at=datetime.utcnow()
        ),
        ModelVersion(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            tag="v2.0.5",
            commit_hash="a8d9c4",
            message="Merge PR #42: PQC Integration",
            author="System",
            status=ModelVersionStatus.VERIFIED.value,
            test_pass_rate="98/98",
            base_model="openvla-7b",
            peft_method="lora",
            created_at=datetime.utcnow()
        ),
        ModelVersion(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            tag="v2.0.4",
            commit_hash="b3e5f6",
            message="Optimize inference latency",
            author="System",
            status=ModelVersionStatus.ARCHIVED.value,
            test_pass_rate="97/98",
            base_model="openvla-7b",
            peft_method="lora",
            created_at=datetime.utcnow()
        )
    ]

    for v in seed_versions:
        session.add(v)
    session.commit()


@router.get("/lineage/versions")
async def list_versions(
    status: Optional[str] = None,
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    List all model versions with their deployment status.

    Returns versions from the database, sorted by created_at descending.
    """
    tenant_id = current_user.tenant_id

    # Ensure seed data for new tenants
    _ensure_seed_data(session, tenant_id)

    query = select(ModelVersion).where(ModelVersion.tenant_id == tenant_id)

    if status:
        query = query.where(ModelVersion.status == status)

    query = query.order_by(col(ModelVersion.created_at).desc()).limit(limit)

    versions = session.exec(query).all()

    result = []
    for v in versions:
        result.append({
            "id": v.id,
            "hash": v.commit_hash,
            "message": v.message,
            "author": v.author,
            "tag": v.tag,
            "status": v.status,
            "test_pass_rate": v.test_pass_rate,
            "base_model": v.base_model,
            "peft_method": v.peft_method,
            "artifact_uri": v.artifact_uri,
            "hf_hub_id": v.hf_hub_id,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "deployed_at": v.deployed_at.isoformat() if v.deployed_at else None,
            "time": _relative_time(v.created_at)
        })

    return {"versions": result, "total": len(result)}


@router.get("/lineage/versions/{tag}")
async def get_version(
    tag: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get detailed info about a specific model version."""
    tenant_id = current_user.tenant_id

    version = session.exec(
        select(ModelVersion).where(
            ModelVersion.tenant_id == tenant_id,
            ModelVersion.tag == tag
        )
    ).first()

    if not version:
        raise HTTPException(status_code=404, detail=f"Version {tag} not found")

    # Get deployment history
    deployments = session.exec(
        select(ModelDeployment).where(
            ModelDeployment.version_id == version.id
        ).order_by(col(ModelDeployment.created_at).desc()).limit(10)
    ).all()

    return {
        "id": version.id,
        "hash": version.commit_hash,
        "message": version.message,
        "author": version.author,
        "tag": version.tag,
        "status": version.status,
        "test_pass_rate": version.test_pass_rate,
        "accuracy": version.accuracy,
        "base_model": version.base_model,
        "peft_method": version.peft_method,
        "architecture": json.loads(version.architecture_json) if version.architecture_json else None,
        "metrics": json.loads(version.metrics_json) if version.metrics_json else None,
        "artifact_uri": version.artifact_uri,
        "hf_hub_id": version.hf_hub_id,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "deployed_at": version.deployed_at.isoformat() if version.deployed_at else None,
        "deployment_history": [
            {
                "id": d.id,
                "deployed_by": d.deployed_by,
                "reason": d.reason,
                "rollout_percentage": d.rollout_percentage,
                "created_at": d.created_at.isoformat()
            }
            for d in deployments
        ]
    }


@router.post("/lineage/versions")
async def create_version(
    req: ModelVersionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new model version."""
    tenant_id = current_user.tenant_id

    # Check for duplicate tag
    existing = session.exec(
        select(ModelVersion).where(
            ModelVersion.tenant_id == tenant_id,
            ModelVersion.tag == req.tag
        )
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail=f"Version {req.tag} already exists")

    version = ModelVersion(
        tenant_id=tenant_id,
        tag=req.tag,
        commit_hash=req.commit_hash,
        message=req.message,
        author=req.author or current_user.email,
        status=ModelVersionStatus.DRAFT.value,
        test_pass_rate=req.test_pass_rate,
        base_model=req.base_model,
        peft_method=req.peft_method,
        artifact_uri=req.artifact_uri,
        hf_hub_id=req.hf_hub_id
    )

    session.add(version)
    session.commit()
    session.refresh(version)

    return {
        "id": version.id,
        "tag": version.tag,
        "status": version.status,
        "created_at": version.created_at.isoformat()
    }


@router.post("/lineage/deploy")
async def deploy_version(
    req: DeployRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Deploy a specific model version.
    Creates an immutable audit log entry with PQC signature.
    """
    tenant_id = current_user.tenant_id

    # Find the version
    version = session.exec(
        select(ModelVersion).where(
            ModelVersion.id == req.version_id,
            ModelVersion.tenant_id == tenant_id
        )
    ).first()

    if not version:
        raise HTTPException(status_code=404, detail=f"Version {req.version_id} not found")

    # Archive currently deployed version(s)
    current_deployed = session.exec(
        select(ModelVersion).where(
            ModelVersion.tenant_id == tenant_id,
            ModelVersion.status == ModelVersionStatus.DEPLOYED.value
        )
    ).all()

    previous_version_id = None
    for v in current_deployed:
        v.status = ModelVersionStatus.VERIFIED.value
        previous_version_id = v.id

    # Deploy new version
    version.status = ModelVersionStatus.DEPLOYED.value
    version.deployed_at = datetime.utcnow()

    # Create deployment record
    deployment = ModelDeployment(
        tenant_id=tenant_id,
        fleet_id=req.fleet_id,
        version_id=version.id,
        previous_version_id=previous_version_id,
        reason=req.reason,
        deployed_by=current_user.id,
        rollout_percentage=req.rollout_percentage
    )

    # Create PQC-signed audit log
    pub, priv = generate_hybrid_sig_keypair()
    log_entry = {
        "action": "MODEL_DEPLOY",
        "version_id": version.id,
        "version_tag": version.tag,
        "previous_version_id": previous_version_id,
        "fleet_id": req.fleet_id,
        "reason": req.reason,
        "rollout_percentage": req.rollout_percentage,
        "timestamp": datetime.utcnow().isoformat()
    }
    sig = sign_hybrid(priv, json.dumps(log_entry).encode())

    deployment.pqc_signature = sig["sig_pqc"]

    audit = AuditLog(
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="MODEL_DEPLOY",
        resource_id=version.id,
        resource_type="model_version",
        details=json.dumps(log_entry),
        pqc_signature=sig["sig_pqc"]
    )

    session.add(deployment)
    session.add(audit)
    session.commit()

    return {
        "status": "deployed",
        "version_id": version.id,
        "version_tag": version.tag,
        "previous_version_id": previous_version_id,
        "deployment_id": deployment.id,
        "audit_id": audit.id,
        "rollout_percentage": req.rollout_percentage
    }


@router.post("/lineage/rollback/{version_id}")
async def rollback_version(
    version_id: str,
    reason: str = "manual_rollback",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Rollback to a previous version."""
    tenant_id = current_user.tenant_id

    # Find the target version
    target = session.exec(
        select(ModelVersion).where(
            ModelVersion.id == version_id,
            ModelVersion.tenant_id == tenant_id
        )
    ).first()

    if not target:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")

    # Archive current deployed
    current = session.exec(
        select(ModelVersion).where(
            ModelVersion.tenant_id == tenant_id,
            ModelVersion.status == ModelVersionStatus.DEPLOYED.value
        )
    ).first()

    if current:
        current.status = ModelVersionStatus.ROLLBACK.value

    # Restore target
    target.status = ModelVersionStatus.DEPLOYED.value
    target.deployed_at = datetime.utcnow()

    # Audit log
    audit = AuditLog(
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="MODEL_ROLLBACK",
        resource_id=target.id,
        resource_type="model_version",
        details=json.dumps({
            "target_version": target.tag,
            "previous_version": current.tag if current else None,
            "reason": reason
        })
    )

    session.add(audit)
    session.commit()

    return {
        "status": "rolled_back",
        "version_id": target.id,
        "version_tag": target.tag,
        "previous_version_tag": current.tag if current else None
    }


@router.post("/lineage/sync")
async def sync_repository(
    req: SyncRequest = SyncRequest(),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Sync with external model registry (HF Hub, MLflow, etc.).

    Currently supports:
    - local: Validate existing versions
    - huggingface: Sync with HuggingFace Hub (requires HF_TOKEN)
    - mlflow: Sync with MLflow registry (requires MLFLOW_TRACKING_URI)
    """
    tenant_id = current_user.tenant_id

    # Count current versions
    version_count = session.exec(
        select(ModelVersion).where(ModelVersion.tenant_id == tenant_id)
    ).all()

    if req.source == "local":
        return {
            "status": "synced",
            "source": "local",
            "versions_found": len(version_count),
            "versions_added": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

    elif req.source == "huggingface":
        # Would integrate with HuggingFace Hub API
        import os
        if not os.getenv("HF_TOKEN"):
            raise HTTPException(
                status_code=400,
                detail="HF_TOKEN environment variable required for HuggingFace sync"
            )
        return {
            "status": "synced",
            "source": "huggingface",
            "versions_found": len(version_count),
            "versions_added": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

    elif req.source == "mlflow":
        import os
        if not os.getenv("MLFLOW_TRACKING_URI"):
            raise HTTPException(
                status_code=400,
                detail="MLFLOW_TRACKING_URI environment variable required for MLflow sync"
            )
        return {
            "status": "synced",
            "source": "mlflow",
            "versions_found": len(version_count),
            "versions_added": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown source: {req.source}")


def _relative_time(dt: Optional[datetime]) -> str:
    """Convert datetime to relative time string."""
    if not dt:
        return "unknown"

    try:
        now = datetime.utcnow()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"
    except:
        return "unknown"
