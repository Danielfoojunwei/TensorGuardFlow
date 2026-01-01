"""
Proprietary Enterprise Extensions (Stubs)
This module marks the boundary for Enterprise features.
"""

def check_entitlement(user: str, feature: str) -> bool:
    # Community mode: All features allowed for local testing
    return True

def log_audit_event(event: dict):
    # Community mode: No-op
    pass
