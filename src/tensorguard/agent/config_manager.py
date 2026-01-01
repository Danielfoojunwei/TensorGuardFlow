"""
Configuration Manager - Agent Config Sync

Handles synchronization of configuration between the local agent and the control plane.
Persists configuration to disk for offline resilience.
"""

import os
import json
import time
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from ..schemas.unified_config import AgentConfig

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages the lifecycle of the Agent's configuration.
    
    Responsibilities:
    1. Load initial config from disk/env.
    2. Sync with Control Plane (Heartbeat).
    3. Notify listeners of config changes (hot-reload).
    4. Persist updates to disk.
    """
    
    def __init__(
        self,
        config_path: str = "config/agent_config.json",
        fleet_api_key: Optional[str] = None
    ):
        # Sanitize path to prevent traversal if it ever comes from an untrusted source
        # and ensure we don't use sensitive system paths like /var/lib/ without absolute intent
        if ".." in config_path or config_path.startswith("/") or config_path.startswith("\\"):
            logger.warning(f"Unsafe config path detected: {config_path}. Sanitizing to local config directory.")
            config_path = os.path.join("config", os.path.basename(config_path))
            
        self.config_path = Path(config_path)
        self.fleet_api_key = fleet_api_key or os.environ.get("TG_FLEET_API_KEY")
        self.timeout = 15 # Default timeout for Control Plane sync
        
        self.current_config: Optional[AgentConfig] = None
        self._listeners: list[Callable[[AgentConfig], None]] = []

    def _save_local(self, config: AgentConfig):
        """Save configuration to disk with safety checks."""
        try:
            # Ensure we are saving in a subfolder relative to CWD if not absolute
            if not self.config_path.is_absolute():
                 abs_path = Path(os.getcwd()) / self.config_path
            else:
                 abs_path = self.config_path
            
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write pattern to prevent corrupt config on disk
            temp_path = abs_path.with_suffix(".tmp")
            temp_path.write_text(config.json(indent=2))
            os.replace(temp_path, abs_path)
            
        except Exception as e:
            logger.error(f"Failed to save local config: {e}")
        
    def add_listener(self, callback: Callable[[AgentConfig], None]):
        """Register a callback for config updates."""
        self._listeners.append(callback)
        
    def _notify_listeners(self):
        """Notify all listeners of new config."""
        if not self.current_config:
            return
        
        for listener in self._listeners:
            try:
                listener(self.current_config)
            except Exception as e:
                logger.error(f"Config listener failed: {e}")

    def load_local(self) -> AgentConfig:
        """Load configuration from local storage or defaults."""
        config_data = {}
        
        if self.config_path.exists():
            try:
                config_data = json.loads(self.config_path.read_text())
                logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load local config: {e}")
        
        # Env vars override
        if not config_data.get("fleet_id"):
             config_data["fleet_id"] = os.environ.get("TG_FLEET_ID", "unknown")
            
        if not config_data.get("agent_name"):
            import socket
            config_data["agent_name"] = os.environ.get("TG_AGENT_NAME", socket.gethostname())
            
        try:
            self.current_config = AgentConfig(**config_data)
        except Exception as e:
            logger.warning(f"Invalid local config, using defaults: {e}")
            self.current_config = AgentConfig(
                agent_name="fallback",
                fleet_id="unknown"
            )
            
        return self.current_config

    def sync_with_control_plane(self) -> bool:
        """
        Sync configuration with the Control Plane.
        
        Returns True if config changed.
        """
        if not self.current_config:
            self.load_local()
            
        if not self.fleet_api_key:
            logger.warning("No API key, running in offline/local mode")
            return False
            
        url = f"{self.current_config.control_plane_url}/api/v1/config/agent/sync"
        
        try:
            payload = {
                "name": self.current_config.agent_name,
                "fleet_id": self.current_config.fleet_id,
                # Report current status/version if needed
            }
            
            headers = {
                "X-TG-Fleet-API-Key": self.fleet_api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            new_config_data = response.json()
            new_config = AgentConfig(**new_config_data)
            
            # Persist if changed
            if new_config != self.current_config:
                logger.info("Configuration updated from Control Plane")
                self.current_config = new_config
                self._save_local(new_config)
                self._notify_listeners()
                return True
                
            return False
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Authentication failed: Invalid API Key")
            else:
                logger.error(f"Sync failed: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return False
