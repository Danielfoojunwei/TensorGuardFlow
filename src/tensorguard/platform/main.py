from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .api import endpoints
import os

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

# Helper to init DB on startup
@app.on_event("startup")
def on_startup():
    init_db()

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

# Serve UI
app.mount("/", StaticFiles(directory="public", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
