"""
Tier 1: Task-Aware Edge Gating API.
Controls the local LoRA adapter gating and telemetry stream on edge nodes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

from ..database import get_session
from ..models.settings_models import SystemSetting
from ..auth import get_current_user
from ..models.core import User

router = APIRouter()

class EdgeNodeConfig(BaseModel):
    node_id: str
    gating_enabled: bool
    local_threshold: float
    task_whitelist: List[str]

# In-memory mock state for edge nodes (in prod, this would sync via MQTT/gRPC)
EDGE_NODES = {
    "node-001": {"gating_enabled": True, "local_threshold": 0.15, "task_whitelist": ["pick_and_place", "welding"]},
    "node-002": {"gating_enabled": True, "local_threshold": 0.10, "task_whitelist": ["inspection"]},
    "node-003": {"gating_enabled": False, "local_threshold": 0.0, "task_whitelist": ["all"]}
}

@router.get("/edge/nodes")
async def list_edge_nodes(session: Session = Depends(get_session)):
    """List all connected edge nodes and their gating status."""
    return [{"id": k, **v} for k, v in EDGE_NODES.items()]

@router.post("/edge/config")
async def update_edge_config(
    req: EdgeNodeConfig, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update gating configuration for a specific edge node."""
    if req.node_id not in EDGE_NODES:
        raise HTTPException(status_code=404, detail="Edge node not found")
    
    EDGE_NODES[req.node_id] = {
        "gating_enabled": req.gating_enabled,
        "local_threshold": req.local_threshold,
        "task_whitelist": req.task_whitelist
    }
    
    return {"status": "updated", "node_id": req.node_id, "config": EDGE_NODES[req.node_id]}

@router.get("/edge/telemetry")
async def get_edge_telemetry(node_id: str = None):
    """Get real-time gating telemetry (simulated)."""
    import random
    
    # Simulate a stream of gating decisions
    telemetry = []
    nodes = [node_id] if node_id else list(EDGE_NODES.keys())
    
    for nid in nodes:
        status = EDGE_NODES.get(nid, {})
        if not status.get("gating_enabled", False):
            continue
            
        for _ in range(5):
            prob = random.random()
            threshold = status.get("local_threshold", 0.1)
            decision = "PASS" if prob > threshold else "BLOCK"
            telemetry.append({
                "node_id": nid,
                "timestamp": datetime.utcnow().isoformat(),
                "task": random.choice(status.get("task_whitelist", ["unknown"])),
                "relevance_score": round(prob, 4),
                "threshold": threshold,
                "decision": decision
            })
            
    return sorted(telemetry, key=lambda x: x["timestamp"], reverse=True)
