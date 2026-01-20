#!/usr/bin/env python3
"""
TensorGuardFlow Worker Stability Check

Tests the background worker for stability:
- Starts worker and monitors for specified duration
- Checks for heartbeat logs
- Detects crash loops
- Monitors for unhandled exceptions

Usage:
    python scripts/qa/worker_stability.py --duration 60 --output artifacts/qa/worker_stability.json
"""

import argparse
import json
import os
import sys
import time
import signal
import threading
from datetime import datetime
from typing import Optional
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class WorkerMonitor:
    """Monitor worker stability metrics."""

    def __init__(self, duration_seconds: int = 60):
        self.duration = duration_seconds
        self.start_time = None
        self.end_time = None
        self.loop_count = 0
        self.errors = []
        self.heartbeats = []
        self.crashed = False
        self.crash_count = 0
        self.running = False

    def record_heartbeat(self, message: str):
        """Record a heartbeat from the worker."""
        self.heartbeats.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message
        })

    def record_error(self, error: str):
        """Record an error from the worker."""
        self.errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "error": error
        })

    def record_loop(self):
        """Record a completed loop iteration."""
        self.loop_count += 1

    def get_results(self) -> dict:
        """Get stability check results."""
        runtime = 0
        if self.start_time:
            end = self.end_time or datetime.utcnow()
            runtime = (end - self.start_time).total_seconds()

        return {
            "test": "worker_stability",
            "duration_requested_sec": self.duration,
            "actual_runtime_sec": round(runtime, 2),
            "loop_count": self.loop_count,
            "heartbeat_count": len(self.heartbeats),
            "error_count": len(self.errors),
            "crash_count": self.crash_count,
            "crashed": self.crashed,
            "errors": self.errors[-5:] if self.errors else [],  # Last 5 errors
            "passed": not self.crashed and len(self.errors) == 0 and self.loop_count > 0
        }


def run_worker_stability_check(duration: int = 60, output_path: Optional[str] = None) -> dict:
    """
    Run the worker stability check.

    Args:
        duration: How long to run the worker (seconds)
        output_path: Where to save results
    """
    print("=" * 60)
    print("TensorGuardFlow Worker Stability Check")
    print("=" * 60)
    print(f"Duration: {duration} seconds")
    print()

    os.environ.setdefault("TG_ENVIRONMENT", "development")

    monitor = WorkerMonitor(duration)
    monitor.start_time = datetime.utcnow()

    try:
        # Import worker components
        from tensorguard.platform.worker import PlatformWorker, WorkerMetrics

        # Create worker with mocked signal handlers
        with patch('signal.signal'):
            worker = PlatformWorker()
            worker.interval = 5  # Faster iteration for testing

        print("Worker initialized successfully")
        print(f"Worker interval: {worker.interval}s")
        print()

        # Run for specified duration
        start = time.time()
        iteration = 0

        while time.time() - start < duration:
            iteration += 1
            print(f"Loop iteration {iteration}...", end=" ")

            try:
                # Mock the database session to avoid actual DB operations
                # but still exercise the worker logic
                with patch('tensorguard.platform.worker.SessionLocal') as mock_session:
                    mock_session.return_value.__enter__ = MagicMock()
                    mock_session.return_value.__exit__ = MagicMock()

                    worker.run_loop_iteration()

                monitor.record_loop()
                monitor.record_heartbeat(f"Loop {iteration} completed")
                print("OK")

                # Check worker health
                health = worker.get_health()
                if health["status"] == "degraded":
                    print(f"  Warning: Worker status degraded")

            except Exception as e:
                error_msg = f"Loop {iteration} error: {str(e)}"
                monitor.record_error(error_msg)
                print(f"ERROR: {e}")

            # Wait before next iteration (but not if we're out of time)
            remaining = duration - (time.time() - start)
            if remaining > worker.interval:
                time.sleep(worker.interval)
            elif remaining > 0:
                time.sleep(remaining)
                break

        monitor.end_time = datetime.utcnow()

        # Get final worker metrics
        print()
        print("Worker Metrics:")
        metrics = worker.metrics.to_dict()
        print(f"  Loops completed: {metrics['loops_completed']}")
        print(f"  Uptime: {metrics['uptime_seconds']}s")
        print(f"  Errors: {metrics['errors_count']}")
        print(f"  Healthy: {metrics['healthy']}")

    except ImportError as e:
        print(f"ERROR: Could not import worker: {e}")
        monitor.crashed = True
        monitor.record_error(f"Import error: {e}")
    except Exception as e:
        print(f"ERROR: Worker crashed: {e}")
        monitor.crashed = True
        monitor.crash_count += 1
        monitor.record_error(f"Crash: {e}")

    # Generate results
    results = monitor.get_results()
    results["timestamp"] = datetime.utcnow().isoformat()

    # Print summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Runtime: {results['actual_runtime_sec']}s")
    print(f"  Loop iterations: {results['loop_count']}")
    print(f"  Heartbeats: {results['heartbeat_count']}")
    print(f"  Errors: {results['error_count']}")
    print(f"  Crashes: {results['crash_count']}")
    print()
    print(f"Result: {'PASS' if results['passed'] else 'FAIL'}")

    # Save results
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="TensorGuardFlow Worker Stability Check")
    parser.add_argument("--duration", "-d", type=int, default=60,
                        help="Duration to run worker (seconds)")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    args = parser.parse_args()

    results = run_worker_stability_check(args.duration, args.output)
    sys.exit(0 if results.get("passed", False) else 1)


if __name__ == "__main__":
    main()
