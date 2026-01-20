"""
Telemetry Ingest Benchmarks

Measure throughput and latency for telemetry batch ingestion.
"""

import asyncio
import hashlib
import json
import random
import string
import time
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx

from .config import BenchmarkConfig, DEFAULT_CONFIG
from .metrics import BenchmarkResult, MetricsCollector, format_result_table


def generate_device_id() -> str:
    """Generate a realistic device ID."""
    return f"device-{uuid.uuid4().hex[:12]}"


def generate_batch_id() -> str:
    """Generate a unique batch ID."""
    return f"batch-{uuid.uuid4().hex}"


def generate_telemetry_message(
    device_id: str, topic: str = "telemetry.stage"
) -> dict[str, Any]:
    """Generate a realistic telemetry message."""
    timestamp_ns = int(time.time() * 1e9)

    if topic == "telemetry.stage":
        return {
            "topic": topic,
            "timestamp_ns": timestamp_ns,
            "payload": {
                "device_id": device_id,
                "stage": random.choice(
                    ["capture", "embed", "gate", "peft", "shield", "sync", "pull"]
                ),
                "status": random.choice(["success", "success", "success", "error"]),
                "latency_ms": random.uniform(10, 500),
                "metrics": {
                    "throughput": random.uniform(100, 10000),
                    "memory_mb": random.uniform(100, 2000),
                },
            },
        }
    elif topic == "telemetry.system":
        return {
            "topic": topic,
            "timestamp_ns": timestamp_ns,
            "payload": {
                "device_id": device_id,
                "cpu_percent": random.uniform(0, 100),
                "memory_percent": random.uniform(20, 90),
                "disk_percent": random.uniform(10, 80),
                "network_rx_bytes": random.randint(0, 1000000),
                "network_tx_bytes": random.randint(0, 1000000),
                "uptime_seconds": random.randint(0, 86400 * 30),
            },
        }
    else:
        return {
            "topic": topic,
            "timestamp_ns": timestamp_ns,
            "payload": {"device_id": device_id, "data": "test"},
        }


def generate_batch(
    fleet_id: str,
    device_id: str,
    batch_size: int,
    topics: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Generate a telemetry batch payload."""
    if topics is None:
        topics = ["telemetry.stage", "telemetry.system"]

    messages = [
        generate_telemetry_message(device_id, random.choice(topics))
        for _ in range(batch_size)
    ]

    return {
        "batch_id": generate_batch_id(),
        "device_info": {
            "device_id": device_id,
            "fleet_id": fleet_id,
            "hostname": f"host-{device_id[:8]}",
            "platform": "linux",
            "version": "2.3.0",
        },
        "messages": messages,
    }


class IngestBenchmark:
    """Benchmark telemetry ingestion throughput."""

    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.token: Optional[str] = None
        self.fleet_id: Optional[str] = None
        self.fleet_api_key: Optional[str] = None

    async def setup(self, client: httpx.AsyncClient) -> bool:
        """Set up authentication and fleet for testing."""
        # Authenticate
        try:
            response = await client.post(
                f"{self.config.url}/auth/token",
                data={
                    "username": self.config.admin_email,
                    "password": self.config.admin_password,
                },
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
            else:
                print(f"Auth failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"Auth error: {e}")
            return False

        auth_headers = {"Authorization": f"Bearer {self.token}"}

        # Get or create fleet
        try:
            response = await client.get(
                f"{self.config.url}/fleets", headers=auth_headers
            )
            if response.status_code == 200:
                fleets = response.json()
                if fleets:
                    self.fleet_id = fleets[0]["id"]
                    self.fleet_api_key = fleets[0].get("api_key")

            if not self.fleet_id:
                response = await client.post(
                    f"{self.config.url}/fleets",
                    headers=auth_headers,
                    json={
                        "name": "ingest-benchmark-fleet",
                        "description": "Telemetry ingest benchmark",
                    },
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    self.fleet_id = data.get("id")
                    self.fleet_api_key = data.get("api_key")

        except Exception as e:
            print(f"Fleet setup error: {e}")

        # Use config API key if set
        if self.config.fleet_api_key:
            self.fleet_api_key = self.config.fleet_api_key

        return bool(self.fleet_id)

    async def bench_ingest(
        self,
        client: httpx.AsyncClient,
        batch_size: int,
        num_devices: int,
        duration: int,
        concurrent: int,
        warmup: int = 5,
    ) -> BenchmarkResult:
        """Benchmark telemetry ingestion at specified parameters."""
        name = f"ingest_batch{batch_size}_dev{num_devices}"
        collector = MetricsCollector(name)

        # Pre-generate device IDs
        device_ids = [generate_device_id() for _ in range(num_devices)]

        url = f"{self.config.url}/telemetry/ingest"
        headers = {}

        # Use Fleet auth if available
        if self.fleet_api_key:
            headers["Authorization"] = f"Fleet {self.fleet_api_key}"
        elif self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async def make_ingest_request(device_id: str) -> tuple[float, bool, int, int, Optional[str]]:
            """Make a single ingest request."""
            batch = generate_batch(self.fleet_id or "default", device_id, batch_size)
            payload = json.dumps(batch)
            payload_bytes = len(payload.encode())

            start = time.perf_counter()
            try:
                response = await client.post(
                    url,
                    headers={**headers, "Content-Type": "application/json"},
                    content=payload,
                )
                latency_ms = (time.perf_counter() - start) * 1000

                if response.status_code == 200:
                    return latency_ms, True, batch_size, payload_bytes, None
                else:
                    return (
                        latency_ms,
                        False,
                        0,
                        payload_bytes,
                        f"{response.status_code}: {response.text[:100]}",
                    )
            except Exception as e:
                latency_ms = (time.perf_counter() - start) * 1000
                return latency_ms, False, 0, 0, str(e)

        async def worker(stop_event: asyncio.Event, record: bool = True) -> None:
            """Worker that continuously sends batches."""
            while not stop_event.is_set():
                device_id = random.choice(device_ids)
                latency_ms, success, events, bytes_sent, error = await make_ingest_request(device_id)
                if record:
                    collector.record_request(
                        latency_ms, success, events=events, bytes_sent=bytes_sent, error=error
                    )
                # Small delay between requests
                await asyncio.sleep(0.01)

        # Warmup
        print(f"  Warming up ({warmup}s)...")
        warmup_stop = asyncio.Event()
        warmup_tasks = [
            asyncio.create_task(worker(warmup_stop, record=False))
            for _ in range(concurrent)
        ]
        await asyncio.sleep(warmup)
        warmup_stop.set()
        await asyncio.gather(*warmup_tasks, return_exceptions=True)

        # Benchmark
        print(f"  Running ingest benchmark ({duration}s, {concurrent} clients, batch={batch_size})...")
        collector.start()
        bench_stop = asyncio.Event()
        bench_tasks = [
            asyncio.create_task(worker(bench_stop, record=True))
            for _ in range(concurrent)
        ]
        await asyncio.sleep(duration)
        bench_stop.set()
        collector.stop()
        await asyncio.gather(*bench_tasks, return_exceptions=True)

        return collector.get_result(
            description=f"Telemetry ingest: {batch_size} events/batch, {num_devices} devices",
            config={
                "batch_size": batch_size,
                "num_devices": num_devices,
                "concurrent_clients": concurrent,
                "duration_seconds": duration,
                "warmup_seconds": warmup,
            },
            thresholds={
                "p95_ms": self.config.latency_p95_threshold_ms,
                "p99_ms": self.config.latency_p99_threshold_ms,
                "max_error_rate": self.config.max_error_rate,
            },
        )

    async def run_all(self) -> list[BenchmarkResult]:
        """Run all ingest benchmarks."""
        results = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            print("\nSetting up ingest benchmarks...")
            if not await self.setup(client):
                print("Setup failed, using default fleet")

            # Test different batch sizes
            for batch_size in self.config.batch_sizes:
                print(f"\n[Batch Size: {batch_size}] Benchmarking telemetry ingest")
                result = await self.bench_ingest(
                    client,
                    batch_size=batch_size,
                    num_devices=self.config.num_simulated_devices,
                    duration=self.config.duration_seconds,
                    concurrent=self.config.concurrent_clients,
                    warmup=self.config.warmup_seconds,
                )
                print(format_result_table(result))
                results.append(result)

        return results


async def run_ingest_benchmarks(
    config: Optional[BenchmarkConfig] = None,
) -> list[BenchmarkResult]:
    """Entry point for ingest benchmarks."""
    benchmark = IngestBenchmark(config)
    return await benchmark.run_all()


if __name__ == "__main__":
    import sys

    results = asyncio.run(run_ingest_benchmarks())

    # Summary
    print("\n" + "=" * 60)
    print("INGEST BENCHMARK SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"  [{status}] {result.name}: "
            f"p95={result.latency.p95_ms:.1f}ms, "
            f"events/s={result.throughput.events_per_second:.1f}"
        )

    print(f"\nTotal: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
