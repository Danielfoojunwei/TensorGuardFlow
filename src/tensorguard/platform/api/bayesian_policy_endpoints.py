"""
Tier 3: Bayesian Evaluation Policy API.
Administers probabilistic gating rules and deployment gates.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import json
import random

from ..database import get_session
from ..models.settings_models import SystemSetting
from ..auth import get_current_user
from ..models.core import User

router = APIRouter()

class PolicyRule(BaseModel):
    id: str
    metric: str
    operator: str  # lt, gt, eq
    threshold: float
    weight: float
    active: bool

class BayesianGateConfig(BaseModel):
    min_confidence_score: float # 0.0 - 1.0
    auto_deploy_enabled: bool
    evaluation_mode: str # "strict", "probabilistic", "monitor_only"

# Mock policy state
POLICY_RULES = [
    {"id": "rule-01", "metric": "privacy.epsilon", "operator": "lt", "threshold": 2.0, "weight": 0.4, "active": True},
    {"id": "rule-02", "metric": "performance.latency_ms", "operator": "lt", "threshold": 50.0, "weight": 0.3, "active": True},
    {"id": "rule-03", "metric": "safety.collision_rate", "operator": "lt", "threshold": 0.01, "weight": 0.3, "active": True}
]

BAYESIAN_STATE = {
    "posterior_confidence": 0.92,
    "prior_belief": 0.85,
    "evidence_count": 142
}

@router.get("/policy/bayesian/config")
async def get_policy_config(session: Session = Depends(get_session)):
    """Get current Bayesian gating configuration."""
    # Retrieve from SystemSettings or defaults
    config = {
        "min_confidence_score": 0.9,
        "auto_deploy_enabled": False,
        "evaluation_mode": "strict"
    }
    
    settings = session.exec(select(SystemSetting).where(
        SystemSetting.key.in_(["min_confidence_score", "auto_deploy_enabled", "evaluation_mode"])
    )).all()
    
    for s in settings:
        if s.key == "min_confidence_score":
            config[s.key] = float(s.value)
        elif s.key == "auto_deploy_enabled":
            config[s.key] = s.value == "true"
        else:
            config[s.key] = s.value
            
    return {"config": config, "rules": POLICY_RULES, "state": BAYESIAN_STATE}

@router.post("/policy/bayesian/rules")
async def update_rules(
    rules: List[PolicyRule], 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update policy rules definition."""
    global POLICY_RULES
    POLICY_RULES = [r.dict() for r in rules]
    return {"status": "updated", "count": len(POLICY_RULES)}

@router.post("/policy/bayesian/evaluate")
async def trigger_evaluation(
    run_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger an on-demand Bayesian evaluation for a specific run.
    Simulates posterior update based on run metrics.
    """
    # Simulate Evaluation
    score = 0.0
    valid_weight = 0.0
    
    metrics = {
        "privacy.epsilon": random.uniform(0.5, 2.5),
        "performance.latency_ms": random.uniform(20, 100),
        "safety.collision_rate": random.uniform(0.0, 0.05)
    }
    
    results = []
    
    for rule in POLICY_RULES:
        if not rule["active"]:
            continue
            
        val = metrics.get(rule["metric"])
        passed = False
        if rule["operator"] == "lt":
            passed = val < rule["threshold"]
        elif rule["operator"] == "gt":
            passed = val > rule["threshold"]
            
        if passed:
            score += rule["weight"]
        
        valid_weight += rule["weight"]
        results.append({
            "rule_id": rule["id"],
            "metric": rule["metric"],
            "value": val,
            "passed": passed
        })
        
    final_score = score / valid_weight if valid_weight > 0 else 0
    decision = "DEPLOY" if final_score > 0.8 else "REJECT"
    
    return {
        "run_id": run_id,
        "decision": decision,
        "confidence_score": final_score,
        "details": results,
        "metrics": metrics
    }
