"""
Proprietary Certification Engine (Production Gate)
"""
import logging

from ..utils.environment import is_production

logger = logging.getLogger(__name__)


def certify_artifact(artifact_id: str):
    if is_production():
        raise RuntimeError("Certification engine is not available in production builds.")
    logger.warning("Certification stub invoked in non-production mode.")
    return {"certified": False, "mode": "community"}
