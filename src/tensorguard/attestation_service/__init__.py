"""
Proprietary Attestation Service (Production Gate)
"""
import logging

from ..utils.environment import is_production

logger = logging.getLogger(__name__)


def attest_node(node_id: str):
    if is_production():
        raise RuntimeError("Attestation service is not available in production builds.")
    logger.warning("Attestation service stub invoked in non-production mode.")
    return {"status": "unattested", "reason": "community_mode"}
