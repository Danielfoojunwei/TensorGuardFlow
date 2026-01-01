"""
Edge Agent Uploader

Reliably uploads spooled messages to the Enablement Service.
Implements exponential backoff and batching.
"""

import time
import threading
import logging
import requests
import json
from typing import Optional

from .spooler import Spooler

logger = logging.getLogger(__name__)

class Uploader(threading.Thread):
    def __init__(
        self, 
        spooler: Spooler, 
        target_url: str, 
        api_key: str,
        batch_size: int = 50,
        interval: float = 1.0
    ):
        super().__init__(daemon=True)
        self.spooler = spooler
        self.target_url = target_url
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }
        self.batch_size = batch_size
        self.interval = interval
        self.running = False
        
    def run(self):
        self.running = True
        logger.info(f"Uploader started. Target: {self.target_url}")
        
        failures = 0
        
        while self.running:
            try:
                # 1. Peek
                batch = self.spooler.peek_batch(self.batch_size)
                if not batch:
                    time.sleep(self.interval)
                    continue
                
                # 2. Upload
                payload = {
                    "batch_id": time.time(),
                    "messages": batch
                }
                
                response = requests.post(
                    f"{self.target_url}/ingest", 
                    json=payload, 
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code in [200, 201, 202]:
                    # 3. Ack (Delete)
                    ids = [m['id'] for m in batch]
                    self.spooler.ack_batch(ids)
                    logger.debug(f"Uploaded {len(ids)} messages")
                    failures = 0 # Reset backoff
                else:
                    logger.warning(f"Upload failed: {response.status_code} {response.text}")
                    failures += 1
                    self._backoff(failures)

            except Exception as e:
                logger.error(f"Upload error: {e}")
                failures += 1
                self._backoff(failures)
                
    def _backoff(self, failures: int):
        sleep_time = min(self.interval * (2 ** (failures - 1)), 60)
        logger.info(f"Retrying in {sleep_time}s...")
        time.sleep(sleep_time)

    def stop(self):
        self.running = False
        self.join()
