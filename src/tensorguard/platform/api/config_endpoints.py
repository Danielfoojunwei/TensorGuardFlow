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

async def verify_agent_api_key(
    x_tg_fleet_api_key: Optional[str] = Header(None)
) -> str:
    """Dependency to verify Fleet API Key."""
    if not x_tg_fleet_api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    # In real impl, verify against Fleet.api_key_hash
    return x_tg_fleet_api_key

@router.post("/agent/sync", response_model=AgentConfig)
async def sync_agent_config(
    agent_info: Dict[str, Any],
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_agent_api_key)
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
    
    # 3. Construct effective config
    # Merge Fleet Policy + Default Config
    
    return AgentConfig(
        agent_name=agent_name,
        fleet_id=fleet_id or "unknown",
        control_plane_url="http://localhost:8000",
        identity={
            "enabled": True,
            "scan_interval_seconds": 3600
        },
        network={
            "enabled": True,
            "defense_mode": "front"
        },
        ml={
            "enabled": True,
            "model_type": "pi0"
        }
    )
