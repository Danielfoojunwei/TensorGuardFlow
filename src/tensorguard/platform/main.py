from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from .database import init_db, check_db_health
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Environment configuration
TG_ENVIRONMENT = os.getenv("TG_ENVIRONMENT", "development")
TG_ALLOWED_ORIGINS = os.getenv("TG_ALLOWED_ORIGINS", "*").split(",")
TG_ENABLE_SECURITY_HEADERS = os.getenv("TG_ENABLE_SECURITY_HEADERS", "true").lower() == "true"

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses for production hardening."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers (OWASP recommendations)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS for production (only over HTTPS)
        if TG_ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy (relaxed for SPA)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:;"
        )

        return response

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
    version="2.3.0",
    lifespan=lifespan
)

# Security headers middleware (first in chain)
if TG_ENABLE_SECURITY_HEADERS:
    app.add_middleware(SecurityHeadersMiddleware)

# GZip compression for responses > 1KB (60-70% bandwidth savings)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS - configurable via environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=TG_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output structure for dev convenience
os.makedirs("public", exist_ok=True)


# --- Health Check Endpoints ---

@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    Returns system health including database connectivity.
    """
    db_health = check_db_health()

    health_status = {
        "status": "healthy" if db_health["status"] == "healthy" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.3.0",
        "environment": TG_ENVIRONMENT,
        "checks": {
            "database": db_health
        }
    }

    return health_status


@app.get("/ready", tags=["health"])
async def readiness_check():
    """
    Kubernetes readiness probe.
    Returns 200 if the service can handle requests.
    """
    db_health = check_db_health()

    if db_health["status"] != "healthy":
        return Response(
            content='{"ready": false, "reason": "database unavailable"}',
            status_code=503,
            media_type="application/json"
        )

    return {"ready": True}


@app.get("/live", tags=["health"])
async def liveness_check():
    """
    Kubernetes liveness probe.
    Returns 200 if the process is alive.
    """
    return {"alive": True}

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

# Model Lineage (Version Control)
from .api import lineage_endpoints
app.include_router(lineage_endpoints.router, prefix="/api/v1", tags=["lineage"])

# VLA (Vision-Language-Action) for Robotics
from .api import vla_endpoints
app.include_router(vla_endpoints.router, prefix="/api/v1", tags=["vla"])

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
