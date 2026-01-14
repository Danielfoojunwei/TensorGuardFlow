"""
Proprietary Recommendation Engine (Production Gate)
"""
import logging

from ..utils.environment import is_production

logger = logging.getLogger(__name__)


def get_recommendations(model_id: str):
    if is_production():
        raise RuntimeError("Recommendation engine is not available in production builds.")
    logger.warning("Recommendation stub invoked in non-production mode.")
    return []
