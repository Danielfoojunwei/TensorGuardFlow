"""
TensorGuard Platform Worker.

Standalone process for running background jobs, detached from the web API.
Prevents duplicate execution in multi-worker/multi-replica deployments.

Features:
- Identity certificate renewal
- Telemetry aggregation
- Stale job cleanup
- Feature flag control
- Graceful shutdown
- Health checks

Usage:
    python -m tensorguard.platform.worker

Or with PYTHONPATH:
    PYTHONPATH=src python -m tensorguard.platform.worker

Environment Variables:
    TG_WORKER_INTERVAL: Seconds between worker loop iterations (default: 10)
    TG_WORKER_IDENTITY_RENEWAL: Enable identity renewal (default: true)
    TG_WORKER_TELEMETRY_AGGREGATION: Enable telemetry aggregation (default: true)
    TG_WORKER_JOB_CLEANUP: Enable job cleanup (default: true)
"""

import os
import time
import signal
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from sqlmodel import select, func

from tensorguard.platform.database import SessionLocal
from tensorguard.identity.scheduler import RenewalScheduler
from tensorguard.platform.models.identity_models import IdentityRenewalJob, RenewalJobStatus
from tensorguard.platform.models.core import Job, JobStatus
from tensorguard.utils.feature_flags import (
    FeatureFlags,
    worker_identity_renewal_enabled,
    worker_telemetry_aggregation_enabled,
    worker_job_cleanup_enabled,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("tensorguard.worker")


@dataclass
class WorkerMetrics:
    """Metrics tracking for worker health monitoring."""
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_loop_at: Optional[datetime] = None
    loops_completed: int = 0
    identity_jobs_processed: int = 0
    telemetry_batches_processed: int = 0
    jobs_cleaned: int = 0
    errors_count: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None

    def record_error(self, error: str) -> None:
        """Record an error occurrence."""
        self.errors_count += 1
        self.last_error = error
        self.last_error_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for health endpoint."""
        uptime = (datetime.utcnow() - self.started_at).total_seconds()
        return {
            "started_at": self.started_at.isoformat(),
            "uptime_seconds": uptime,
            "last_loop_at": self.last_loop_at.isoformat() if self.last_loop_at else None,
            "loops_completed": self.loops_completed,
            "identity_jobs_processed": self.identity_jobs_processed,
            "telemetry_batches_processed": self.telemetry_batches_processed,
            "jobs_cleaned": self.jobs_cleaned,
            "errors_count": self.errors_count,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "healthy": self.errors_count == 0 or (
                self.last_error_at and
                (datetime.utcnow() - self.last_error_at).total_seconds() > 300
            ),
        }


class GracefulExit:
    """Handle graceful shutdown signals."""

    def __init__(self):
        self.exit_now = False
        self._lock = threading.Lock()
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)

    def handle_exit(self, signum, frame):
        logger.info(f"Received exit signal ({signum}). Gracefully shutting down...")
        with self._lock:
            self.exit_now = True

    def should_exit(self) -> bool:
        with self._lock:
            return self.exit_now


class PlatformWorker:
    """
    Main worker class coordinating all background jobs.

    Uses feature flags to enable/disable specific job processors.
    """

    def __init__(self):
        self.metrics = WorkerMetrics()
        self.exiter = GracefulExit()
        self.interval = int(os.getenv("TG_WORKER_INTERVAL", "10"))

        # Log feature flag status at startup
        logger.info("Worker Feature Flags:")
        logger.info(f"  Identity Renewal: {worker_identity_renewal_enabled()}")
        logger.info(f"  Telemetry Aggregation: {worker_telemetry_aggregation_enabled()}")
        logger.info(f"  Job Cleanup: {worker_job_cleanup_enabled()}")

    def process_identity_renewals(self) -> int:
        """
        Process pending identity renewal jobs.

        Returns:
            Number of jobs processed
        """
        if not worker_identity_renewal_enabled():
            return 0

        processed = 0
        try:
            with SessionLocal() as session:
                scheduler = RenewalScheduler(session)

                # Filter for actionable jobs
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
                    (
                        (IdentityRenewalJob.status == RenewalJobStatus.PENDING) &
                        (IdentityRenewalJob.next_retry_at != None) &
                        (IdentityRenewalJob.next_retry_at <= now)
                    )
                )

                jobs = session.exec(statement).all()
                if jobs:
                    logger.info(f"Processing {len(jobs)} pending identity jobs...")
                    for job in jobs:
                        if self.exiter.should_exit():
                            break
                        try:
                            scheduler.advance_job(job.id)
                            processed += 1
                        except Exception as e:
                            logger.error(f"Error advancing job {job.id}: {e}")
                            self.metrics.record_error(f"identity_job_{job.id}: {e}")

        except Exception as e:
            logger.error(f"Identity renewal error: {e}")
            self.metrics.record_error(f"identity_renewal: {e}")

        self.metrics.identity_jobs_processed += processed
        return processed

    def process_telemetry_aggregation(self) -> int:
        """
        Process telemetry data aggregation.

        Returns:
            Number of batches processed
        """
        if not worker_telemetry_aggregation_enabled():
            return 0

        processed = 0
        try:
            # Telemetry aggregation is handled by the ingest endpoint
            # This worker can perform periodic rollups/compaction if needed
            # For now, this is a no-op placeholder for future implementation
            pass

        except Exception as e:
            logger.error(f"Telemetry aggregation error: {e}")
            self.metrics.record_error(f"telemetry_aggregation: {e}")

        self.metrics.telemetry_batches_processed += processed
        return processed

    def cleanup_stale_jobs(self) -> int:
        """
        Clean up stale/stuck jobs.

        Jobs stuck in running state for more than 24 hours are marked as failed.

        Returns:
            Number of jobs cleaned up
        """
        if not worker_job_cleanup_enabled():
            return 0

        cleaned = 0
        try:
            with SessionLocal() as session:
                stale_threshold = datetime.utcnow() - timedelta(hours=24)

                # Find stuck identity renewal jobs
                stuck_renewals = session.exec(
                    select(IdentityRenewalJob).where(
                        IdentityRenewalJob.status.in_([
                            RenewalJobStatus.VALIDATING,
                            RenewalJobStatus.ISSUING,
                            RenewalJobStatus.CSR_REQUESTED,
                            RenewalJobStatus.CHALLENGE_PENDING,
                        ]),
                        IdentityRenewalJob.updated_at < stale_threshold
                    )
                ).all()

                for job in stuck_renewals:
                    if self.exiter.should_exit():
                        break
                    logger.warning(f"Marking stale renewal job as failed: {job.id}")
                    job.status = RenewalJobStatus.FAILED
                    job.error_message = "Job timed out after 24 hours"
                    job.updated_at = datetime.utcnow()
                    session.add(job)
                    cleaned += 1

                # Find stuck platform jobs
                stuck_jobs = session.exec(
                    select(Job).where(
                        Job.status == JobStatus.RUNNING.value,
                        Job.created_at < stale_threshold
                    )
                ).all()

                for job in stuck_jobs:
                    if self.exiter.should_exit():
                        break
                    logger.warning(f"Marking stale platform job as failed: {job.id}")
                    job.status = JobStatus.FAILED.value
                    job.completed_at = datetime.utcnow()
                    session.add(job)
                    cleaned += 1

                if cleaned > 0:
                    session.commit()
                    logger.info(f"Cleaned up {cleaned} stale jobs")

        except Exception as e:
            logger.error(f"Job cleanup error: {e}")
            self.metrics.record_error(f"job_cleanup: {e}")

        self.metrics.jobs_cleaned += cleaned
        return cleaned

    def run_loop_iteration(self) -> None:
        """Run a single iteration of the worker loop."""
        self.process_identity_renewals()
        self.process_telemetry_aggregation()
        self.cleanup_stale_jobs()

        self.metrics.last_loop_at = datetime.utcnow()
        self.metrics.loops_completed += 1

    def run(self) -> None:
        """Main worker loop."""
        logger.info("TensorGuard Background Worker started")
        logger.info(f"Worker interval: {self.interval} seconds")

        while not self.exiter.should_exit():
            try:
                self.run_loop_iteration()
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                self.metrics.record_error(f"worker_loop: {e}")

            # Sleep in small increments to check for exit signal
            for _ in range(self.interval):
                if self.exiter.should_exit():
                    break
                time.sleep(1)

        logger.info("Worker shutdown complete.")
        logger.info(f"Final metrics: {self.metrics.to_dict()}")

    def get_health(self) -> Dict[str, Any]:
        """Get worker health status for monitoring."""
        return {
            "status": "healthy" if self.metrics.to_dict()["healthy"] else "degraded",
            "metrics": self.metrics.to_dict(),
            "feature_flags": FeatureFlags.list_flags(),
        }


def run_worker_loop():
    """Entry point for running the worker."""
    worker = PlatformWorker()
    worker.run()


if __name__ == "__main__":
    run_worker_loop()
