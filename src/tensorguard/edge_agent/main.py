#!/usr/bin/env python3
"""
Edge Agent CLI Entrypoint

Starts the spooler and uploader for telemetry ingestion to the Control Plane.
Uses Fleet Bearer authentication (Authorization: Fleet <api_key>).

Usage:
    python -m tensorguard.edge_agent.main \
        --db-path /var/lib/tensorguard/spool.db \
        --url http://localhost:8000/api/v1/telemetry \
        --fleet-id my-fleet \
        --api-key tg_xxxx

Environment variables can also be used:
    TG_SPOOL_DB_PATH, TG_API_URL, TG_FLEET_ID, TG_FLEET_API_KEY
"""

import argparse
import logging
import os
import signal
import sys
import time

from .spooler import Spooler
from .uploader import Uploader

logging.basicConfig(
    level=os.environ.get("TG_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="TensorGuard Edge Agent - Telemetry Uploader"
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("TG_SPOOL_DB_PATH", "/var/lib/tensorguard/spool.db"),
        help="Path to the SQLite spool database"
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("TG_API_URL", "http://localhost:8000/api/v1/telemetry"),
        help="Control plane telemetry API URL (without /ingest suffix)"
    )
    parser.add_argument(
        "--fleet-id",
        default=os.environ.get("TG_FLEET_ID"),
        help="Fleet ID for authentication"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("TG_FLEET_API_KEY"),
        help="Fleet API key for HMAC authentication"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("TG_BATCH_SIZE", "50")),
        help="Number of messages per upload batch"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("TG_UPLOAD_INTERVAL", "1.0")),
        help="Upload interval in seconds"
    )

    args = parser.parse_args()

    # Validate required arguments
    if not args.fleet_id:
        logger.error("Fleet ID is required. Set --fleet-id or TG_FLEET_ID")
        sys.exit(1)
    if not args.api_key:
        logger.error("API key is required. Set --api-key or TG_FLEET_API_KEY")
        sys.exit(1)

    logger.info(f"Starting Edge Agent Uploader")
    logger.info(f"  Spool DB: {args.db_path}")
    logger.info(f"  API URL: {args.url}")
    logger.info(f"  Fleet ID: {args.fleet_id}")

    # Initialize spooler
    spooler = Spooler(db_path=args.db_path)
    logger.info(f"  Spool size: {spooler.size()} messages")

    # Initialize and start uploader
    uploader = Uploader(
        spooler=spooler,
        target_url=args.url,
        api_key=args.api_key,
        fleet_id=args.fleet_id,
        batch_size=args.batch_size,
        interval=args.interval
    )

    # Handle graceful shutdown
    running = True

    def signal_handler(signum, frame):
        nonlocal running
        logger.info("Received shutdown signal, stopping...")
        running = False
        uploader.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start uploader thread
    uploader.start()

    # Keep main thread alive
    try:
        while running and uploader.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    logger.info("Edge Agent Uploader stopped")


if __name__ == "__main__":
    main()
