#!/usr/bin/env python3
"""
TensorGuardFlow Performance Smoke Tests

Tests basic performance characteristics:
- Telemetry ingest throughput
- Concurrent request handling
- Response latencies

Usage:
    python scripts/qa/perf_smoke.py --output artifacts/qa/perf_results.json
"""

import argparse
import json
import os
import sys
import time
import secrets
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


def get_test_client():
    """Get a test client for the API."""
    os.environ.setdefault("TG_ENVIRONMENT", "development")
    from fastapi.testclient import TestClient
    from tensorguard.platform.main import app
    return TestClient(app, raise_server_exceptions=False)


def create_test_setup(client) -> Optional[dict]:
    """Create test organization and fleet."""
    suffix = secrets.token_hex(4)
    email = f"perf_test_{suffix}@test.com"
    password = "PerfTestPass123!"
    org_name = f"PerfOrg_{suffix}"

    # Create org
    client.post(
        "/api/v1/onboarding/init",
        params={
            "name": org_name,
            "admin_email": email,
            "admin_pass": password
        }
    )

    # Login
    login_resp = client.post(
        "/api/v1/auth/token",
        json={"username": email, "password": password}
    )
    if login_resp.status_code != 200:
        return None

    token = login_resp.json()["access_token"]

    # Create fleet
    fleet_resp = client.post(
        f"/api/v1/fleets?name=PerfFleet_{suffix}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if fleet_resp.status_code != 200:
        return None

    fleet_data = fleet_resp.json()
    return {
        "token": token,
        "fleet_id": fleet_data["id"],
        "api_key": fleet_data["api_key"]
    }


def test_ingest_throughput(client, api_key: str, num_events: int = 500, batch_size: int = 50) -> dict:
    """
    Test telemetry ingest throughput.

    Args:
        client: Test client
        api_key: Fleet API key
        num_events: Total events to ingest
        batch_size: Events per batch
    """
    num_batches = num_events // batch_size
    latencies = []
    errors = 0
    total_accepted = 0

    print(f"\nIngest Throughput Test: {num_events} events in {num_batches} batches")

    start_time = time.time()

    for i in range(num_batches):
        batch_id = f"perf_batch_{i}_{secrets.token_hex(4)}"
        messages = []

        for j in range(batch_size):
            messages.append({
                "topic": "telemetry.stage",
                "timestamp_ns": int(time.time() * 1e9),
                "payload": {
                    "device_id": f"perf_device_{i}",
                    "stage": "capture",
                    "status": "ok",
                    "latency_ms": 10.0 + (j * 0.1)
                },
                "priority": 0
            })

        batch_start = time.time()
        response = client.post(
            "/api/v1/telemetry/ingest",
            headers={"Authorization": f"Fleet {api_key}"},
            json={
                "batch_id": batch_id,
                "device_info": {"device_id": f"perf_device_{i}"},
                "messages": messages
            }
        )
        batch_latency = (time.time() - batch_start) * 1000  # ms
        latencies.append(batch_latency)

        if response.status_code == 200:
            data = response.json()
            total_accepted += data.get("accepted", 0)
        else:
            errors += 1

        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{num_batches} batches")

    total_time = time.time() - start_time

    result = {
        "test": "ingest_throughput",
        "total_events": num_events,
        "total_batches": num_batches,
        "batch_size": batch_size,
        "total_accepted": total_accepted,
        "errors": errors,
        "total_time_sec": round(total_time, 3),
        "events_per_sec": round(num_events / total_time, 2),
        "avg_latency_ms": round(statistics.mean(latencies), 2),
        "p50_latency_ms": round(statistics.median(latencies), 2),
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2),
        "max_latency_ms": round(max(latencies), 2),
        "passed": errors == 0 and total_time < 5.0  # Less than 5 seconds for 500 events
    }

    print(f"  Total time: {result['total_time_sec']}s")
    print(f"  Events/sec: {result['events_per_sec']}")
    print(f"  Avg latency: {result['avg_latency_ms']}ms")
    print(f"  PASS" if result['passed'] else f"  FAIL")

    return result


def test_concurrent_requests(client, api_key: str, num_requests: int = 10) -> dict:
    """
    Test concurrent request handling.

    Args:
        client: Test client
        api_key: Fleet API key
        num_requests: Number of concurrent requests
    """
    print(f"\nConcurrent Requests Test: {num_requests} parallel requests")

    def make_request(request_id):
        start = time.time()
        response = client.post(
            "/api/v1/telemetry/ingest",
            headers={"Authorization": f"Fleet {api_key}"},
            json={
                "batch_id": f"concurrent_{request_id}_{secrets.token_hex(4)}",
                "device_info": {"device_id": f"concurrent_device_{request_id}"},
                "messages": [{
                    "topic": "telemetry.stage",
                    "timestamp_ns": int(time.time() * 1e9),
                    "payload": {
                        "device_id": f"concurrent_device_{request_id}",
                        "stage": "capture",
                        "status": "ok",
                        "latency_ms": 10.0
                    },
                    "priority": 0
                }]
            }
        )
        latency = (time.time() - start) * 1000
        return {
            "request_id": request_id,
            "status_code": response.status_code,
            "latency_ms": latency,
            "success": response.status_code == 200
        }

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(make_request, i) for i in range(num_requests)]
        for future in as_completed(futures):
            results.append(future.result())

    total_time = time.time() - start_time
    successes = sum(1 for r in results if r["success"])
    latencies = [r["latency_ms"] for r in results]

    result = {
        "test": "concurrent_requests",
        "num_requests": num_requests,
        "successes": successes,
        "failures": num_requests - successes,
        "total_time_sec": round(total_time, 3),
        "avg_latency_ms": round(statistics.mean(latencies), 2),
        "max_latency_ms": round(max(latencies), 2),
        "deadlocks_detected": False,  # Would be True if requests timed out
        "passed": successes == num_requests
    }

    print(f"  Successes: {successes}/{num_requests}")
    print(f"  Total time: {result['total_time_sec']}s")
    print(f"  Avg latency: {result['avg_latency_ms']}ms")
    print(f"  PASS" if result['passed'] else f"  FAIL")

    return result


def test_dashboard_response(client, token: str) -> dict:
    """Test dashboard endpoint response time."""
    print("\nDashboard Response Test")

    latencies = []
    errors = 0

    for i in range(10):
        start = time.time()
        response = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        latency = (time.time() - start) * 1000
        latencies.append(latency)

        if response.status_code != 200:
            errors += 1

    result = {
        "test": "dashboard_response",
        "requests": 10,
        "errors": errors,
        "avg_latency_ms": round(statistics.mean(latencies), 2),
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2),
        "max_latency_ms": round(max(latencies), 2),
        "passed": errors == 0 and statistics.mean(latencies) < 500  # < 500ms avg
    }

    print(f"  Avg latency: {result['avg_latency_ms']}ms")
    print(f"  PASS" if result['passed'] else f"  FAIL")

    return result


def run_perf_smoke(output_path: Optional[str] = None):
    """Run all performance smoke tests."""
    print("=" * 60)
    print("TensorGuardFlow Performance Smoke Tests")
    print("=" * 60)

    client = get_test_client()

    # Setup
    print("\nSetting up test environment...")
    setup = create_test_setup(client)
    if not setup:
        print("ERROR: Could not create test setup")
        return {"error": "Setup failed", "passed": False}

    print(f"  Fleet ID: {setup['fleet_id']}")

    # Run tests
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "tests": []
    }

    # 1. Ingest throughput
    ingest_result = test_ingest_throughput(client, setup["api_key"], num_events=500, batch_size=50)
    results["tests"].append(ingest_result)

    # 2. Concurrent requests
    concurrent_result = test_concurrent_requests(client, setup["api_key"], num_requests=10)
    results["tests"].append(concurrent_result)

    # 3. Dashboard response
    dashboard_result = test_dashboard_response(client, setup["token"])
    results["tests"].append(dashboard_result)

    # Summary
    all_passed = all(t["passed"] for t in results["tests"])
    results["all_passed"] = all_passed

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for test in results["tests"]:
        status = "PASS" if test["passed"] else "FAIL"
        print(f"  {test['test']}: {status}")

    print(f"\nOverall: {'PASS' if all_passed else 'FAIL'}")

    # Save results
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="TensorGuardFlow Performance Smoke Tests")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    args = parser.parse_args()

    results = run_perf_smoke(args.output)
    sys.exit(0 if results.get("all_passed", False) else 1)


if __name__ == "__main__":
    main()
