from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import List, Dict, Any
from ..database import get_session
from ..models.enablement_models import PolicyProfile, EnablementJob, GovernanceEvent
from ...core.privacy.ledger import PrivacyLedger

router = APIRouter()
# Simple global ledger instance for the platform
# In a real distributed system, this would aggregate from agents
platform_ledger = PrivacyLedger(storage_path="./platform_privacy.json")

@router.get("/stats")
def get_stats(session: Session = Depends(get_session)):
    """Get aggregate statistics for enablement dashboard."""
    total_jobs = session.exec(select(func.count(EnablementJob.run_id))).one()
    pending_jobs = session.exec(
        select(func.count(EnablementJob.run_id)).where(EnablementJob.status == "PENDING")
    ).one()
    running_jobs = session.exec(
        select(func.count(EnablementJob.run_id)).where(EnablementJob.status == "RUNNING")
    ).one()
    success_jobs = session.exec(
        select(func.count(EnablementJob.run_id)).where(EnablementJob.status == "SUCCESS")
    ).one()
    failed_jobs = session.exec(
        select(func.count(EnablementJob.run_id)).where(EnablementJob.status == "FAILED")
    ).one()
    total_events = session.exec(select(func.count(GovernanceEvent.id))).one()
    
    return {
        "total_jobs": total_jobs,
        "pending_jobs": pending_jobs,
        "running_jobs": running_jobs,
        "success_jobs": success_jobs,
        "failed_jobs": failed_jobs,
        "total_events": total_events,
        "privacy_consumed_epsilon": platform_ledger.total_epsilon,
        "privacy_budget_total": 10.0, # Default budget cap
    }

@router.get("/profiles", response_model=List[PolicyProfile])
def list_profiles(session: Session = Depends(get_session)):
    return session.exec(select(PolicyProfile)).all()

@router.post("/profiles", response_model=PolicyProfile)
def create_profile(profile: PolicyProfile, session: Session = Depends(get_session)):
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile

@router.get("/jobs", response_model=List[EnablementJob])
def list_jobs(session: Session = Depends(get_session)):
    return session.exec(select(EnablementJob)).all()

@router.get("/jobs/{run_id}", response_model=EnablementJob)
def get_job(run_id: str, session: Session = Depends(get_session)):
    job = session.get(EnablementJob, run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/events", response_model=List[GovernanceEvent])
def list_events(session: Session = Depends(get_session)):
    return session.exec(select(GovernanceEvent)).all()
