from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Any, Dict
from pydantic import BaseModel
from datetime import timedelta

from ..database import get_session
from ..models.core import Tenant, User, Fleet, Job
from ..auth import get_current_user, create_access_token, verify_password, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str

class LoginData(BaseModel):
    username: str
    password: str

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: LoginData, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "tenant_id": user.tenant_id}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# --- Tenants ---
@router.post("/onboarding/init", response_model=Tenant)
async def init_tenant(name: str, admin_email: str, admin_pass: str, session: Session = Depends(get_session)):
    """Initialize a new tenant and admin user."""
    try:
        # Check if user exists
        existing_user = session.exec(select(User).where(User.email == admin_email)).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
            
        tenant = Tenant(name=name, plan="Enterprise")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        
        user = User(
            email=admin_email, 
            hashed_password=get_password_hash(admin_pass),
            role="owner",
            tenant_id=tenant.id
        )
        session.add(user)
        session.commit()
        
        return tenant
    except Exception as e:
        print(f"ERROR in init_tenant: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- Fleets ---
@router.get("/fleets", response_model=List[Fleet])
async def get_fleets(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return session.exec(select(Fleet).where(Fleet.tenant_id == current_user.tenant_id)).all()

@router.post("/fleets", response_model=Dict[str, Any])
async def create_fleet(name: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    import secrets
    import hashlib
    
    # Generate a real secure API key
    raw_key = f"tg_{secrets.token_hex(16)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    fleet = Fleet(name=name, tenant_id=current_user.tenant_id, api_key_hash=key_hash)
    session.add(fleet)
    session.commit()
    session.refresh(fleet)
    
    # Return the raw key ONLY once
    return {
        "id": fleet.id,
        "name": fleet.name,
        "api_key": raw_key,
        "instruction": "Save this key! It will not be shown again."
    }

# --- Jobs ---
@router.get("/jobs", response_model=List[Job])
async def get_jobs(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    # Join with Fleet to check Tenant ID
    statement = select(Job).join(Fleet).where(Fleet.tenant_id == current_user.tenant_id)
    return session.exec(statement).all()

@router.post("/jobs", response_model=Job)
async def create_job(fleet_id: str, type: str, config: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    # Verify fleet ownership
    fleet = session.get(Fleet, fleet_id)
    if not fleet or fleet.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Fleet not found")
        
    job = Job(fleet_id=fleet_id, type=type, config_json=config, status="pending")
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
