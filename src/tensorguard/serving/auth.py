"""
Authentication Middleware
"""
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_tenant(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Validate Bearer token.
    For this demo, we accept any token starting with 'tg_'.
    Returns tenant_id.
    """
    token = credentials.credentials
    if not token.startswith("tg_"):
        raise HTTPException(status_code=403, detail="Invalid authentication credentials")
        
    # Extract tenant ID from token (mock: tg_tenant1_secret)
    parts = token.split("_")
    if len(parts) >= 2:
        return parts[1]
        
    return "default_tenant"
