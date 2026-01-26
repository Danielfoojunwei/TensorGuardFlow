"""
Enablement Sidecar Service

FastAPI wrapper for submitting and monitoring Enablement Jobs.
Deployable as a sidecar container in RobOps platforms.

Usage:
    uvicorn services.enablement_sidecar.main:app --port 8001
"""

import logging
import os
import uuid
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

# Import Pipeline
from tensorguard.enablement.external_platform.adapters.filesystem import (
    FilesystemAdapter,
)
from tensorguard.enablement.governance.policy import GovernanceEngine
from tensorguard.enablement.pipelines.run_job import RunContext, run_pipeline

# Configuration from environment
SIDECAR_VERSION = "1.0.0"
RUNS_DIR = os.getenv("TG_SIDECAR_RUNS_DIR", "./runs")
DP_BUDGET_LIMIT = float(os.getenv("TG_SIDECAR_DP_BUDGET", "100.0"))

app = FastAPI(
    title="TensorGuard Enablement Sidecar",
    version=SIDECAR_VERSION,
    description="Sidecar service for enablement job submission and monitoring",
)

logger = logging.getLogger("EnablementSidecar")

# In-memory job store (use Redis/DB for production multi-instance deployments)
job_store: Dict[str, str] = {}

# Adapter setup
adapter = FilesystemAdapter(RUNS_DIR)
governance = GovernanceEngine({"dp_budget_limit": DP_BUDGET_LIMIT})


class JobSubmit(BaseModel):
    """Request model for job submission."""

    robot_id: str
    job_type: str
    config: Dict[str, Any]


class JobStatus(BaseModel):
    """Response model for job status."""

    run_id: str
    status: str
    message: str = ""


def execute_job_bg(run_ctx: RunContext) -> None:
    """Background task wrapper for job execution."""
    try:
        run_pipeline(adapter, run_ctx, governance)
        job_store[run_ctx.run_id] = "COMPLETED"
    except Exception as e:
        logger.error(f"Job {run_ctx.run_id} failed: {e}", exc_info=True)
        job_store[run_ctx.run_id] = f"FAILED: {e}"


@app.post("/jobs", response_model=JobStatus)
async def submit_job(job: JobSubmit, background_tasks: BackgroundTasks) -> JobStatus:
    """Submit a new enablement job for background execution."""
    run_id = str(uuid.uuid4())

    ctx = RunContext(
        run_id=run_id,
        robot_id=job.robot_id,
        job_type=job.job_type,
        config=job.config,
    )

    job_store[run_id] = "QUEUED"
    background_tasks.add_task(execute_job_bg, ctx)

    logger.info(f"Job {run_id} submitted for robot {job.robot_id}")
    return JobStatus(run_id=run_id, status="QUEUED")


@app.get("/jobs/{run_id}", response_model=JobStatus)
async def get_job_status(run_id: str) -> JobStatus:
    """Get the status of a submitted job."""
    if run_id not in job_store:
        # Check filesystem adapter for persisted status
        try:
            run_dir = adapter._get_run_dir(run_id)
            status_path = run_dir / "status.txt"
            if status_path.exists():
                content = status_path.read_text().strip()
                return JobStatus(run_id=run_id, status=content)
        except (IOError, OSError, AttributeError) as e:
            logger.debug(f"Could not read status file for {run_id}: {e}")

        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatus(run_id=run_id, status=job_store[run_id])


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": SIDECAR_VERSION}


@app.get("/ready")
async def ready() -> Dict[str, bool]:
    """Readiness check endpoint."""
    # Check if runs directory is accessible
    try:
        adapter._get_run_dir("test-readiness")
        return {"ready": True}
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")
