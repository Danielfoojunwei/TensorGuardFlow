from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .database import init_db
import os

# Initialize database schema
# In dev mode, we ensure the schema is up to date
init_db()

from .api import endpoints

import asyncio
from contextlib import asynccontextmanager
from .api.identity_endpoints import get_session
from ..identity.scheduler import RenewalScheduler
from .models.identity_models import IdentityRenewalJob, RenewalJobStatus
from sqlmodel import select
from datetime import datetime

async def identity_job_runner():
    """Background task to advance identity renewal jobs."""
    while True:
        try:
            # We need a new session for each iteration
            from .database import Session, engine
            with Session(engine) as session:
                scheduler = RenewalScheduler(session)
                
                # Find actionable jobs
                # 1. Statuses where platform acts immediately
                # 2. Statuses that need polling (ISSUING)
                # 3. PENDING with next_retry_at <= now
                now = datetime.utcnow()
                statement = select(IdentityRenewalJob).where(
                    (IdentityRenewalJob.status.in_([
                        RenewalJobStatus.PENDING,
                        RenewalJobStatus.CSR_RECEIVED,
                        RenewalJobStatus.CHALLENGE_COMPLETE,
                        RenewalJobStatus.ISSUED,
                        RenewalJobStatus.VALIDATING,
                        RenewalJobStatus.ISSUING
                    ])) |
                    ((IdentityRenewalJob.status == RenewalJobStatus.PENDING) & (IdentityRenewalJob.next_retry_at != None) & (IdentityRenewalJob.next_retry_at <= now))
                )
                
                jobs = session.exec(statement).all()
                for job in jobs:
                    try:
                        # Optimistic concurrency: scheduler.advance_job should handle it
                        scheduler.advance_job(job.id)
                    except Exception as e:
                        print(f"Error advancing job {job.id}: {e}")
            
        except Exception as e:
            print(f"Identity job runner loop error: {e}")
            
        await asyncio.sleep(10) # Run every 10 seconds

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background tasks
    task = asyncio.create_task(identity_job_runner())
    yield
    # Shutdown: Stop background tasks
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="TensorGuard Management Platform",
    description="White-label backend for TensorGuard fleets",
    version="2.1.0",
    lifespan=lifespan
)

# GZip compression for responses > 1KB (60-70% bandwidth savings)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output structure for dev convenience
os.makedirs("public", exist_ok=True)

# Routes
app.include_router(endpoints.router, prefix="/api/v1")

# Identity routes
from .api import identity_endpoints
app.include_router(identity_endpoints.router, prefix="/api/v1/identity", tags=["identity"])

# Unified Config routes
from .api import config_endpoints
app.include_router(config_endpoints.router, prefix="/api/v1/config", tags=["config"])

# Enablement routes (Trust Console)
from .api import enablement_endpoints
app.include_router(enablement_endpoints.router, prefix="/api/v1/enablement", tags=["enablement"])

# Runs & Evidence
from .api import runs_endpoints
app.include_router(runs_endpoints.router, prefix="/api/v1", tags=["runs"])

# Community TGSP
from .api import community_tgsp
app.include_router(community_tgsp.router, prefix="/api/community/tgsp", tags=["community-tgsp"])

# PEFT Studio
from .api import peft_endpoints
app.include_router(peft_endpoints.router, prefix="/api/v1/peft", tags=["peft"])

# FedMoE Experts & Skills Library
from .api import fedmoe_endpoints
app.include_router(fedmoe_endpoints.router, prefix="/api/v1/fedmoe", tags=["fedmoe"])

# System Settings
from .api import settings_endpoints
app.include_router(settings_endpoints.router, prefix="/api/v1", tags=["settings"])

# Pipeline Configuration
from .api import pipeline_config_endpoints
app.include_router(pipeline_config_endpoints.router, prefix="/api/v1", tags=["pipeline-config"])

# KMS (Key Management Service)
from .api import kms_endpoints
app.include_router(kms_endpoints.router, prefix="/api/v1", tags=["kms"])

# Advanced 3-Tier Gating & Forensics
from .api import edge_gating_endpoints
app.include_router(edge_gating_endpoints.router, prefix="/api/v1", tags=["edge-gating"])

from .api import skills_library_endpoints
app.include_router(skills_library_endpoints.router, prefix="/api/v1", tags=["skills-library"])

from .api import bayesian_policy_endpoints
app.include_router(bayesian_policy_endpoints.router, prefix="/api/v1", tags=["bayesian-policy"])

from .api import forensics_endpoints
app.include_router(forensics_endpoints.router, prefix="/api/v1", tags=["forensics"])

from .api import integrations_endpoints
app.include_router(integrations_endpoints.router, prefix="/api/v1", tags=["integrations"])

# Enterprise Stubs (Proprietary Boundary)
try:
    from .enterprise import check_entitlement, log_audit_event
    print("Enterprise extensions found.")
except ImportError:
    def check_entitlement(user, feat): return True
    def log_audit_event(ev): pass

# Serve UI
# Single Page Application (SPA) catch-all
from fastapi.responses import FileResponse

# Use absolute path for public directory

# Use absolute path for public directory (Vue Build)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PUBLIC_DIR = os.path.join(BASE_DIR, "frontend", "dist")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Skip API routes (though definition order should handle this)
    if full_path.startswith("api/v1"):
        return None 
        
    file_path = os.path.join(PUBLIC_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    # Default to index.html for SPA
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

# StaticFiles mounting for structured assets if needed
app.mount("/static", StaticFiles(directory=PUBLIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
