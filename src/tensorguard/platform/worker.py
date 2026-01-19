"""
TensorGuard Platform Worker.

Standalone process for running background jobs, detached from the web API.
Prevents duplicate execution in multi-worker/multi-replica deployments.

Usage:
    python -m tensorguard.platform.worker

Or with PYTHONPATH:
    PYTHONPATH=src python -m tensorguard.platform.worker
"""

import os
import time
import signal
import logging
from datetime import datetime
from sqlmodel import select

from tensorguard.platform.database import SessionLocal
from tensorguard.identity.scheduler import RenewalScheduler
from tensorguard.platform.models.identity_models import IdentityRenewalJob, RenewalJobStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("tensorguard.worker")

# Gracefully handle signals
class GracefulExit:
    def __init__(self):
        self.exit_now = False
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)

    def handle_exit(self, signum, frame):
        logger.info(f"Received exit signal ({signum}). Gracefully shutting down...")
        self.exit_now = True

def run_worker_loop():
    """Main loop for identity renewal jobs."""
    exiter = GracefulExit()
    logger.info("TensorGuard Background Worker started")
    
    interval = int(os.getenv("TG_WORKER_INTERVAL", "10"))
    
    while not exiter.exit_now:
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
                    ((IdentityRenewalJob.status == RenewalJobStatus.PENDING) & (IdentityRenewalJob.next_retry_at != None) & (IdentityRenewalJob.next_retry_at <= now))
                )
                
                jobs = session.exec(statement).all()
                if jobs:
                    logger.info(f"Processing {len(jobs)} pending identity jobs...")
                    for job in jobs:
                        if exiter.exit_now:
                            break
                        try:
                            # Advance job logic (includes locking/status transitions)
                            scheduler.advance_job(job.id)
                        except Exception as e:
                            logger.error(f"Error advancing job {job.id}: {e}")
                
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            
        # Sleep in small increments to check for exit signal
        for _ in range(interval):
            if exiter.exit_now:
                break
            time.sleep(1)

    logger.info("Worker shutdown complete.")

if __name__ == "__main__":
    run_worker_loop()
