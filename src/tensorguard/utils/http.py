import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any

from .logging import get_logger
from .exceptions import CommunicationError

logger = get_logger(__name__)

class StandardClient:
    """
    Standard HTTP Client for TensorGuard.
    Enforces timeouts, retries, and standard headers.
    """
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        
        # Configure Retries
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        
        # Standard Headers
        self.session.headers.update({
            "User-Agent": "TensorGuard-Client/1.0",
            "X-TG-Client-Version": "1.0.0"
        })
        if api_key:
            self.session.headers.update({"X-TG-Fleet-API-Key": api_key})

    def request(self, method: str, path: str, timeout: int = 15, **kwargs) -> Dict[str, Any]:
        """Performs a request and handles common errors."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            raise CommunicationError(f"API Error: {e.response.status_code}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Network Error: {e}")
            raise CommunicationError("Failed to connect to Control Plane") from e

def get_standard_client(base_url: str, api_key: Optional[str] = None) -> StandardClient:
    return StandardClient(base_url, api_key)
