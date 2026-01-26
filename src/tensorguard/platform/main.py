from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from .database import check_db_health, SessionLocal
from .middleware import (
    RequestIDMiddleware,
    StructuredLoggingMiddleware,
    RateLimitMiddleware,
    StandardErrorResponse,
    ErrorCodes,
    setup_logging,
    get_request_id,
)
import os
import sys
import logging
import signal
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Set

# Setup structured logging early
setup_logging(os.getenv("TG_LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Global background task registry for graceful shutdown
_background_tasks: Set[asyncio.Task] = set()
_shutdown_event = asyncio.Event()

# Environment configuration
TG_ENVIRONMENT = os.getenv("TG_ENVIRONMENT", "development")
_raw_origins = os.getenv("TG_ALLOWED_ORIGINS", "")
# SECURITY: Default to restrictive CORS in production, permissive only in dev
if _raw_origins:
    TG_ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
elif TG_ENVIRONMENT == "production":
    TG_ALLOWED_ORIGINS = []  # No origins allowed by default in production
    logger.warning("SECURITY: No TG_ALLOWED_ORIGINS configured for production. CORS will reject all origins.")
else:
    TG_ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]
TG_ENABLE_SECURITY_HEADERS = os.getenv("TG_ENABLE_SECURITY_HEADERS", "true").lower() == "true"

# SECURITY: Credentials require explicit origin list (not wildcard)
TG_ALLOW_CREDENTIALS = os.getenv("TG_ALLOW_CREDENTIALS", "false").lower() == "true"
if TG_ALLOW_CREDENTIALS and "*" in TG_ALLOWED_ORIGINS:
    logger.critical("SECURITY ERROR: Cannot use allow_credentials=true with wildcard origin '*'")
    TG_ALLOW_CREDENTIALS = False

# Database schema managed via Alembic migrations (no auto-init)

from .api import endpoints

import asyncio
from contextlib import asynccontextmanager
from .api.identity_endpoints import get_session
from ..identity.scheduler import RenewalScheduler
from .models.identity_models import IdentityRenewalJob, RenewalJobStatus
from .models.core import AuditLog, Fleet
from .models.telemetry_models import TelemetryStageEvent, TelemetrySystemEvent
from sqlmodel import select, func
from ..utils.startup_validation import validate_startup_config
from .. import __version__ as TG_VERSION


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
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:;"
        )

        return response

def _check_vault_accessibility() -> dict:
    """Check if vault directory is accessible and writable."""
    vault_path = Path(os.getenv("TG_VAULT_PATH", "keys"))
    try:
        vault_path.mkdir(parents=True, exist_ok=True)
        test_file = vault_path / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        return {"status": "ok", "path": str(vault_path), "writable": True}
    except Exception as e:
        return {"status": "error", "path": str(vault_path), "writable": False, "error": str(e)}


def _get_startup_banner() -> str:
    """Generate startup banner with version and environment info."""
    demo_mode = os.getenv("TG_DEMO_MODE", "false").lower() == "true"
    demo_flag = " [DEMO MODE]" if demo_mode else ""
    return (
        f"\n"
        f"╔══════════════════════════════════════════════════════════════╗\n"
        f"║  TensorGuard Management Platform v{TG_VERSION:<24}  ║\n"
        f"║  Environment: {TG_ENVIRONMENT:<20}{demo_flag:<24}  ║\n"
        f"╚══════════════════════════════════════════════════════════════╝"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Production-grade lifespan handler with structured startup and shutdown.

    Startup sequence:
    1. Validate configuration (secrets, database, dependencies)
    2. Check database connectivity with timeout
    3. Validate vault path accessibility
    4. Log startup banner with version info

    Shutdown sequence:
    1. Signal background tasks to stop
    2. Wait for tasks with timeout
    3. Close database connections
    4. Log clean shutdown
    """
    startup_start = datetime.utcnow()

    # Phase 1: Configuration validation
    logger.info("[STARTUP] Phase 1: Validating configuration...")
    try:
        validate_startup_config(
            "platform",
            require_database=True,
            require_secret_key=True,
            require_key_master=False,  # Only required if vault encryption is used
            enforce_migrations=True,
            required_dependencies=[
                ("cryptography", "Install cryptography: pip install cryptography>=41.0"),
            ],
        )
    except Exception as e:
        logger.critical(f"[STARTUP] Configuration validation failed: {e}")
        raise

    # Phase 2: Database connectivity check with timeout
    logger.info("[STARTUP] Phase 2: Checking database connectivity...")
    db_health = check_db_health()
    if db_health["status"] != "healthy":
        logger.critical(f"[STARTUP] Database not reachable: {db_health}")
        if TG_ENVIRONMENT == "production":
            raise RuntimeError(f"Database not reachable: {db_health.get('error', 'unknown')}")
    else:
        logger.info(f"[STARTUP] Database healthy: pool_size={db_health.get('pool_size', 'N/A')}")

    # Phase 3: Vault accessibility check
    logger.info("[STARTUP] Phase 3: Checking vault accessibility...")
    vault_status = _check_vault_accessibility()
    if vault_status["status"] != "ok":
        logger.warning(f"[STARTUP] Vault not writable: {vault_status}")
        if TG_ENVIRONMENT == "production":
            raise RuntimeError(f"Vault not writable: {vault_status.get('error', 'unknown')}")
    else:
        logger.info(f"[STARTUP] Vault accessible at {vault_status['path']}")

    # Phase 4: Migration status check
    logger.info("[STARTUP] Phase 4: Checking migration status...")
    try:
        from .db_migration import check_migrations
        migration_status = check_migrations()
        if not migration_status["is_current"]:
            logger.warning(
                f"[STARTUP] Database has {migration_status['pending_count']} pending migrations. "
                f"Current: {migration_status['current_revision']}, Head: {migration_status['head_revision']}"
            )
        else:
            logger.info(f"[STARTUP] Database schema is current (revision: {migration_status['current_revision']})")
        # Store for readyz endpoint
        app.state.migration_status = migration_status
    except Exception as e:
        logger.warning(f"[STARTUP] Could not check migrations: {e}")
        app.state.migration_status = {"is_current": True, "error": str(e)}

    # Phase 5: Store startup state for health endpoints
    app.state.startup_complete = True
    app.state.startup_time = startup_start
    app.state.db_health = db_health
    app.state.vault_status = vault_status

    startup_duration = (datetime.utcnow() - startup_start).total_seconds()
    logger.info(_get_startup_banner())
    logger.info(f"[STARTUP] Platform ready in {startup_duration:.2f}s")

    yield

    # === SHUTDOWN SEQUENCE ===
    logger.info("[SHUTDOWN] Beginning graceful shutdown...")
    shutdown_start = datetime.utcnow()

    # Signal shutdown to any background tasks
    _shutdown_event.set()

    # Cancel and wait for background tasks with timeout
    if _background_tasks:
        logger.info(f"[SHUTDOWN] Cancelling {len(_background_tasks)} background tasks...")
        for task in _background_tasks:
            task.cancel()

        try:
            await asyncio.wait_for(
                asyncio.gather(*_background_tasks, return_exceptions=True),
                timeout=10.0
            )
            logger.info("[SHUTDOWN] Background tasks terminated cleanly")
        except asyncio.TimeoutError:
            logger.warning("[SHUTDOWN] Some background tasks did not terminate in time")

    # Note: Database connection pool is managed by SQLAlchemy and will be
    # cleaned up automatically. Explicit disposal can be added if needed.

    shutdown_duration = (datetime.utcnow() - shutdown_start).total_seconds()
    logger.info(f"[SHUTDOWN] Graceful shutdown complete in {shutdown_duration:.2f}s")


def register_background_task(task: asyncio.Task) -> None:
    """Register a background task for tracking and graceful shutdown."""
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def is_shutting_down() -> bool:
    """Check if the application is shutting down."""
    return _shutdown_event.is_set()

app = FastAPI(
    title="TensorGuard Management Platform",
    description="White-label backend for TensorGuard fleets",
    version=TG_VERSION,
    lifespan=lifespan
)

# Security headers middleware (first in chain)
if TG_ENABLE_SECURITY_HEADERS:
    app.add_middleware(SecurityHeadersMiddleware)

# GZip compression for responses > 1KB (60-70% bandwidth savings)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS - configurable via environment with secure defaults
app.add_middleware(
    CORSMiddleware,
    allow_origins=TG_ALLOWED_ORIGINS,
    allow_credentials=TG_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID",
        # HMAC auth headers for edge agent telemetry
        "X-TG-Fleet-Id", "X-TG-Timestamp", "X-TG-Nonce", "X-TG-Signature",
    ],
)

# Rate limiting middleware (before logging to track limited requests)
# Configurable via TG_RATE_LIMIT_GENERAL, TG_RATE_LIMIT_AUTH, TG_RATE_LIMIT_BURST
TG_ENABLE_RATE_LIMIT = os.getenv("TG_ENABLE_RATE_LIMIT", "true").lower() == "true"
if TG_ENABLE_RATE_LIMIT:
    app.add_middleware(RateLimitMiddleware)

# Metrics middleware for request tracking (if prometheus available)
TG_ENABLE_METRICS = os.getenv("TG_ENABLE_METRICS", "true").lower() == "true"
if TG_ENABLE_METRICS:
    try:
        from ..observability.otel import MetricsMiddleware, setup_observability
        app.add_middleware(MetricsMiddleware)
        # Setup observability at module load (will be re-called safely in lifespan)
        setup_observability("tensorguard-platform")
    except ImportError:
        logger.debug("Metrics middleware not available (prometheus_client not installed)")

# Request ID and structured logging middleware
# Note: Middleware is executed in reverse order of registration
# RequestIDMiddleware must be added last so it runs first
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

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
        "version": TG_VERSION,
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


# --- Production Health Endpoints (Kubernetes-standard naming) ---

@app.get("/healthz", tags=["health"])
async def healthz():
    """
    Kubernetes-style liveness probe.
    Returns 200 if process is alive - no dependency checks.
    Use for: Kubernetes livenessProbe
    """
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/readyz", tags=["health"])
async def readyz(request: Request):
    """
    Kubernetes-style readiness probe with comprehensive dependency checks.
    Returns 200 ONLY if ALL of the following are true:
    - Database is reachable
    - Database schema is up-to-date (migrations current)
    - Vault path is accessible

    Use for: Kubernetes readinessProbe, load balancer health checks

    Returns structured JSON with actionable diagnostics on failure.
    """
    checks = {
        "database": {"status": "unknown"},
        "migrations": {"status": "unknown"},
        "vault": {"status": "unknown"},
    }
    all_passed = True

    # Check 1: Database connectivity
    db_health = check_db_health()
    if db_health["status"] == "healthy":
        checks["database"] = {"status": "pass", "pool": db_health}
    else:
        checks["database"] = {"status": "fail", "error": db_health.get("error", "unknown")}
        all_passed = False

    # Check 2: Migration status (schema up-to-date)
    try:
        migration_status = getattr(request.app.state, "migration_status", None)
        if migration_status is None:
            from .db_migration import check_migrations
            migration_status = check_migrations()

        if migration_status.get("is_current", False):
            checks["migrations"] = {
                "status": "pass",
                "revision": migration_status.get("current_revision"),
            }
        else:
            checks["migrations"] = {
                "status": "fail",
                "current": migration_status.get("current_revision"),
                "head": migration_status.get("head_revision"),
                "pending_count": migration_status.get("pending_count", 0),
                "action": "Run 'alembic upgrade head' or set TG_AUTO_MIGRATE=true",
            }
            all_passed = False
    except Exception as e:
        checks["migrations"] = {"status": "fail", "error": str(e)}
        all_passed = False

    # Check 3: Vault accessibility
    vault_status = getattr(request.app.state, "vault_status", None)
    if vault_status is None:
        vault_status = _check_vault_accessibility()

    if vault_status.get("status") == "ok":
        checks["vault"] = {"status": "pass", "path": vault_status.get("path")}
    else:
        checks["vault"] = {
            "status": "fail",
            "path": vault_status.get("path"),
            "error": vault_status.get("error", "not writable"),
        }
        all_passed = False

    response_body = {
        "ready": all_passed,
        "status": "ok" if all_passed else "not_ready",
        "version": TG_VERSION,
        "environment": TG_ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }

    if not all_passed:
        return Response(
            content=__import__("json").dumps(response_body),
            status_code=503,
            media_type="application/json",
        )

    return response_body


# --- API v1 Health Aliases (for frontend compatibility) ---
# Frontend expects /api/v1/health but we have /health at root

@app.get("/api/v1/health", tags=["health"])
async def health_check_api_v1():
    """
    Health check endpoint alias under /api/v1 for frontend compatibility.
    Delegates to the main /health endpoint.
    """
    return await health_check()


@app.get("/api/v1/status", tags=["health"])
async def status_api_v1():
    """
    Status endpoint for frontend compatibility.
    Returns system status summary.
    """
    db_health = check_db_health()

    return {
        "status": "operational" if db_health["status"] == "healthy" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": TG_VERSION,
        "environment": TG_ENVIRONMENT,
        "database": db_health["status"],
    }


@app.get("/metrics", tags=["observability"])
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.

    Returns a Prometheus-formatted response derived from live database data.
    """
    try:
        with SessionLocal() as session:
            audit_total = session.exec(select(func.count()).select_from(AuditLog)).one()
            fleet_total = session.exec(select(func.count()).select_from(Fleet)).one()
            stage_events_total = session.exec(
                select(func.count()).select_from(TelemetryStageEvent)
            ).one()
            system_events_total = session.exec(
                select(func.count()).select_from(TelemetrySystemEvent)
            ).one()

        lines = [
            "# TensorGuard Platform Metrics",
            "# TYPE tensorguard_info gauge",
            f"tensorguard_info{{version=\"{TG_VERSION}\"}} 1",
            "# TYPE tensorguard_audit_logs_total counter",
            f"tensorguard_audit_logs_total {audit_total}",
            "# TYPE tensorguard_fleets_total gauge",
            f"tensorguard_fleets_total {fleet_total}",
            "# TYPE tensorguard_telemetry_stage_events_total counter",
            f"tensorguard_telemetry_stage_events_total {stage_events_total}",
            "# TYPE tensorguard_telemetry_system_events_total counter",
            f"tensorguard_telemetry_system_events_total {system_events_total}",
        ]
        content = "\n".join(lines) + "\n"
    except Exception as exc:
        logger.error(f"Metrics collection failed: {exc}")
        return Response(
            content='{"error": "metrics collection failed"}',
            status_code=503,
            media_type="application/json",
        )
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8"
    )


# --- Debug System Endpoint (Admin Only) ---

from .auth import get_current_user
from .models.core import User, OrganizationRole, OrganizationMembership
from .models.telemetry_models import FleetDevice

@app.get("/api/v1/debug/system", tags=["debug"])
async def debug_system_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Debug endpoint for system diagnostics.

    Returns comprehensive system status including:
    - Database connectivity and pool status
    - Pending renewal jobs
    - Telemetry counts
    - Fleet counts
    - Worker status (if available)

    Requires: Authenticated user with ADMIN or OWNER role
    """
    # Check user role (must be admin or owner)
    from .auth import get_user_org_role
    user_role = get_user_org_role(current_user.id, current_user.tenant_id, SessionLocal())

    # Allow if legacy ORG_ADMIN or new OWNER/ADMIN
    from .models.core import UserRole
    is_admin = (
        current_user.role in [UserRole.ORG_ADMIN, UserRole.SITE_ADMIN] or
        (user_role and user_role in [OrganizationRole.OWNER, OrganizationRole.ADMIN])
    )

    if not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Debug endpoint requires admin privileges"
        )

    request_id = getattr(request.state, "request_id", None) or get_request_id() or "unknown"

    try:
        with SessionLocal() as session:
            # Database counts
            fleet_count = session.exec(select(func.count()).select_from(Fleet)).one()
            device_count = session.exec(select(func.count()).select_from(FleetDevice)).one()
            audit_count = session.exec(select(func.count()).select_from(AuditLog)).one()
            stage_events_count = session.exec(
                select(func.count()).select_from(TelemetryStageEvent)
            ).one()
            system_events_count = session.exec(
                select(func.count()).select_from(TelemetrySystemEvent)
            ).one()

            # Pending renewal jobs
            pending_renewals = session.exec(
                select(func.count()).select_from(IdentityRenewalJob).where(
                    IdentityRenewalJob.status.in_([
                        RenewalJobStatus.PENDING.value,
                        RenewalJobStatus.RUNNING.value
                    ])
                )
            ).one()

            # Membership count for current org
            membership_count = session.exec(
                select(func.count()).select_from(OrganizationMembership).where(
                    OrganizationMembership.organization_id == current_user.tenant_id
                )
            ).one()

        db_health = check_db_health()

        return {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "version": TG_VERSION,
            "environment": TG_ENVIRONMENT,
            "debug": {
                "database": {
                    "status": db_health["status"],
                    "pool_info": db_health.get("pool_info", {}),
                },
                "counts": {
                    "fleets": fleet_count,
                    "devices": device_count,
                    "audit_logs": audit_count,
                    "stage_events": stage_events_count,
                    "system_events": system_events_count,
                    "org_memberships": membership_count,
                },
                "pending_jobs": {
                    "renewal_jobs": pending_renewals,
                },
                "feature_flags": {
                    "security_headers_enabled": TG_ENABLE_SECURITY_HEADERS,
                    "cors_credentials": TG_ALLOW_CREDENTIALS,
                },
            },
            "user": {
                "email": current_user.email,
                "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
                "org_role": user_role.value if user_role else None,
            },
        }
    except Exception as exc:
        logger.error(f"[{request_id}] Debug endpoint error: {exc}", exc_info=True)
        return StandardErrorResponse.create(
            code=ErrorCodes.INTERNAL_ERROR,
            message="Failed to collect debug information",
            status_code=500,
            details={"error": str(exc)},
            request_id=request_id,
        )


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

# Community TGSP (mounted at both paths for backward compatibility)
from .api import community_tgsp
app.include_router(community_tgsp.router, prefix="/api/community/tgsp", tags=["community-tgsp"])
# Also mount at /api/v1/tgsp for frontend compatibility
app.include_router(community_tgsp.router, prefix="/api/v1/tgsp", tags=["tgsp"])

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

# Dashboard & Status endpoints (real-time metrics)
from .api import dashboard_endpoints
app.include_router(dashboard_endpoints.router, prefix="/api/v1", tags=["dashboard"])

# VLA (Vision-Language-Action) for Robotics
from .api import vla_endpoints
app.include_router(vla_endpoints.router, prefix="/api/v1", tags=["vla"])

# Production Telemetry Ingestion & Query
from .api import telemetry_endpoints
app.include_router(telemetry_endpoints.router, prefix="/api/v1", tags=["telemetry"])

# Deployment Management (Canary, A/B, Shadow, Rollback)
from .api import deployment_endpoints
app.include_router(deployment_endpoints.router, prefix="/api/v1", tags=["deployments"])

# Enterprise Stubs (Proprietary Boundary)
try:
    from .enterprise import check_entitlement, log_audit_event
    print("Enterprise extensions found.")
except ImportError:
    def check_entitlement(user, feat): return True
    def log_audit_event(ev): pass

# Serve UI
# Single Page Application (SPA) catch-all
from fastapi.responses import FileResponse, HTMLResponse

# Use absolute path for public directory (Vue Build)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PUBLIC_DIR = os.path.join(BASE_DIR, "frontend", "dist")

# Check if frontend build exists
FRONTEND_AVAILABLE = os.path.isdir(PUBLIC_DIR) and os.path.isfile(os.path.join(PUBLIC_DIR, "index.html"))

if not FRONTEND_AVAILABLE:
    logger.warning(
        f"Frontend build not found at {PUBLIC_DIR}. "
        "Run 'cd frontend && npm install && npm run build' to build the UI."
    )


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Skip API routes (though definition order should handle this)
    if full_path.startswith("api/") or full_path.startswith("health") or full_path.startswith("ready") or full_path.startswith("live") or full_path.startswith("metrics"):
        return None

    # If frontend is not built, return a helpful message
    if not FRONTEND_AVAILABLE:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>TensorGuard Platform</title></head>
            <body style="font-family: sans-serif; padding: 2rem;">
                <h1>TensorGuard Platform API</h1>
                <p>The frontend has not been built yet.</p>
                <p>To build the UI, run:</p>
                <pre style="background: #f4f4f4; padding: 1rem; border-radius: 4px;">
cd frontend
npm install
npm run build
                </pre>
                <p>API endpoints are available at <a href="/docs">/docs</a></p>
            </body>
            </html>
            """,
            status_code=200
        )

    file_path = os.path.join(PUBLIC_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    # Default to index.html for SPA
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return HTMLResponse(content="<h1>Not Found</h1>", status_code=404)


# StaticFiles mounting for structured assets (only if frontend exists)
if FRONTEND_AVAILABLE:
    app.mount("/static", StaticFiles(directory=PUBLIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
