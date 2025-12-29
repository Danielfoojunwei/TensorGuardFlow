import logging
from ..models.core import Job

logger = logging.getLogger(__name__)

async def dispatch_job_to_fleet(job: Job):
    """
    Dispatches a job to the remote fleet via the specific adapter.
    
    Supported Adapters:
    - Open-RMF (HTTP/WebSocket)
    - VDA5050 (MQTT)
    - Formant (Agent API)
    """
    logger.info(f"Dispatching JOB {job.id} [Type: {job.type}] to Fleet {job.fleet_id}")
    
    # Logic to load adapter based on Fleet config would go here
    # e.g. adapter = get_adapter(job.fleet.type)
    # adapter.send(job)
    
    logger.info("Dispatch successful (Mock)")
    return True
