import logging
from typing import Optional, Dict, Any
from ...utils.http import StandardClient

logger = logging.getLogger(__name__)

class IdentityAgentClient(StandardClient):
    """
    HTTP Client for identity agents with Fleet Bearer authentication.

    Authentication: Uses Fleet Bearer token (Authorization: Fleet <api_key>).
    The raw API key is sent to the backend, which hashes it with SHA256 and
    compares against the stored api_key_hash in the Fleet table.
    """
    def __init__(self, base_url: str, fleet_id: str, api_key: str):
        super().__init__(base_url)
        self.fleet_id = fleet_id
        self.api_key = api_key

    def authenticated_request(self, method: str, path: str, json_data: Any = None, **kwargs) -> Dict[str, Any]:
        """Perform an authenticated request to the platform using Fleet Bearer auth."""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Fleet {self.api_key}"

        return self.request(method, path, json=json_data, headers=headers, **kwargs)

    # Keep signed_request as alias for backwards compatibility
    def signed_request(self, method: str, path: str, json_data: Any = None, **kwargs) -> Dict[str, Any]:
        """Alias for authenticated_request (backwards compatibility)."""
        return self.authenticated_request(method, path, json_data, **kwargs)
