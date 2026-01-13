"""
Edge Agent Manager

Integrates the ROS 2 Edge Agent components (Node, Spooler, Uploader) 
into the Unified Agent Daemon lifecycle.
"""

import threading
import logging
import os
from typing import Dict, Any, Optional

from .config_manager import ConfigManager
from ..edge_agent.spooler import Spooler
from ..edge_agent.uploader import Uploader
from ..edge_agent.ros2_node import AgentNode, HAS_ROS2

if HAS_ROS2:
    import rclpy

logger = logging.getLogger(__name__)

class EdgeAgentManager:
    """
    Manages the ROS 2 Data Collection subsystem.
    """
    def __init__(self, config: Any, config_manager: ConfigManager):
        self.config = config
        self.config_manager = config_manager
        self.running = False
        self.spooler: Optional[Spooler] = None
        self.uploader: Optional[Uploader] = None
        self.ros_node: Optional[AgentNode] = None
        self.ros_thread: Optional[threading.Thread] = None

    def start(self):
        if self.running: return
        self.running = True
        logger.info("Starting Edge Agent Manager...")
        
        # 1. Spooler
        data_dir = getattr(self.config, 'data_dir', './storage')
        if ".." in data_dir or data_dir.startswith("/") or data_dir.startswith("\\"):
             # Local dev fallback
             data_dir = "storage"
             
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "spool.db")
        self.spooler = Spooler(db_path)
        
        # 2. Uploader - Point to real telemetry ingestion endpoint
        base_url = self.config.control_plane_url + "/api/v1"
        api_key = self.config.api_key or os.environ.get("TG_FLEET_API_KEY")
        fleet_id = getattr(self.config, 'fleet_id', os.environ.get("TG_FLEET_ID", ""))

        if not api_key:
            logger.warning("No API Key found. Uploader disabled.")
        elif not fleet_id:
            logger.warning("No Fleet ID found. Uploader disabled.")
        else:
            self.uploader = Uploader(
                self.spooler,
                target_url=base_url + "/telemetry",
                api_key=api_key,
                fleet_id=fleet_id,
            )
            self.uploader.start()
            
        # 3. ROS Node
        if HAS_ROS2:
            self.ros_thread = threading.Thread(target=self._run_ros, daemon=True)
            self.ros_thread.start()
        else:
            logger.warning("ROS 2 not found. Log collection disabled.")

    def stop(self):
        logger.info("Stopping Edge Agent Manager...")
        self.running = False
        
        if self.uploader:
            self.uploader.stop()
            
        if self.ros_node and HAS_ROS2 and rclpy.ok():
            self.ros_node.destroy_node()
            rclpy.shutdown()
            
        if self.ros_thread:
            self.ros_thread.join(timeout=2)

    def _run_ros(self):
        """Runs the ROS 2 spin loop in a thread."""
        try:
            rclpy.init()
            # Default ROS topics config (should be from self.config)
            topics = [
                {"name": "/tf", "type": "tf2_msgs/TFMessage"},
                {"name": "/odom", "type": "nav_msgs/Odometry"}
            ]
            self.ros_node = AgentNode(self.spooler, topics)
            rclpy.spin(self.ros_node)
        except Exception as e:
            logger.error(f"ROS Node error: {e}")
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def configure(self, new_config):
        # Update uploader URL/Key if changed
        # Restart ROS node if topics changed
        pass
