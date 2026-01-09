from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .database import init_db
import os

# Initialize database schema immediately to avoid OperationalErrors during import
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

# Enterprise Stubs (Proprietary Boundary)
try:
    from .enterprise import check_entitlement, log_audit_event
    print("Enterprise extensions found.")
except ImportError:
    def check_entitlement(user, feat): return True
    def log_audit_event(ev): pass

# Serve UI
app.mount("/", StaticFiles(directory="public", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
