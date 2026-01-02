from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db, seed_db
import os

# Initialize database schema immediately to avoid OperationalErrors during import
init_db()
seed_db()

from .api import endpoints

app = FastAPI(
    title="TensorGuard Management Platform",
    description="White-label backend for TensorGuard fleets",
    version="2.1.0"
)

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
