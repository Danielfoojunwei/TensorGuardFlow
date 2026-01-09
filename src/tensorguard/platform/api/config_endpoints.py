"""
Configuration Endpoints - Unified Agent Config Management

Endpoints for agents to fetch their configuration and for admins to manage fleet policies.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlmodel import Session, select
from typing import Dict, Any, Optional

from ..database import get_session
from ..models.core import Fleet
from ..auth import get_current_user
from ...schemas.unified_config import AgentConfig, FleetPolicy
from ..models.identity_models import IdentityAgent as AgentDB
from .identity_endpoints import verify_fleet_auth
from ..services.trust_service import TrustService

router = APIRouter()

# --- Admin Routes ---

@router.get("/fleets/{fleet_id}/policy", response_model=FleetPolicy)
async def get_fleet_policy(
    fleet_id: str,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Get the active policy for a fleet."""
    fleet = session.get(Fleet, fleet_id)
    if not fleet or fleet.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Fleet not found")
    
    # In a real impl, this would come from a FleetPolicyDB model
    # For now, return a default/stub policy based on fleet config
    return FleetPolicy(
        fleet_id=fleet.id,
        name=f"Policy for {fleet.name}",
        identity_rules={"auto_renew": True},
        network_rules={"defense_mode": "front"},
        ml_rules={"security_level": "medium"}
    )

@router.put("/fleets/{fleet_id}/policy", response_model=FleetPolicy)
async def update_fleet_policy(
    fleet_id: str,
    policy: FleetPolicy,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Update fleet policy."""
    fleet = session.get(Fleet, fleet_id)
    if not fleet or fleet.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Fleet not found")
    
    # Stub: Save policy to DB
    return policy


# --- Agent Routes ---

# Legacy verify_agent_api_key removed in favor of verify_fleet_auth (HMAC-based)

@router.post("/agent/sync", response_model=AgentConfig)
async def sync_agent_config(
    agent_info: Dict[str, Any],
    session: Session = Depends(get_session),
    fleet: Fleet = Depends(verify_fleet_auth)
):
    """
    Agent heartbeat and config sync.
    
    Agent sends its local info, Server returns the authoritative config.
    """
    # 1. Verify fleet (simplified for demo)
    # fleet = session.exec(select(Fleet).where(...)).first()
    
    # 2. Update/Register Agent in DB
    agent_name = agent_info.get("name", "unknown")
    fleet_id = agent_info.get("fleet_id")
    
    # 3. Construct effective config using TrustService
    trust = TrustService(session).calculate_fleet_trust(fleet.id)
    
    # Directives based on trust score
    security_level = "high" if trust["aggregate_score"] > 85 else "medium"
    if trust["layers"]["transport"]["score"] < 50:
        # Emergency lockdown if identity is compromised or near expiry
        security_level = "fail-safe"
    
    return AgentConfig(
        agent_name=agent_name,
        fleet_id=fleet.id,
        control_plane_url="http://localhost:8000",
        identity={
            "enabled": True,
            "scan_interval_seconds": 3600,
            "trust_score": trust["aggregate_score"]
        },
        network={
            "enabled": True,
            "defense_mode": "front" if security_level != "fail-safe" else "isolated"
        },
        ml={
            "enabled": security_level != "fail-safe",
            "model_type": "pi0",
            "security_level": security_level
        }
    )
