"""
API Latency Benchmarks

Measure response time distributions for key API endpoints.
"""

import asyncio
import json
import time
from typing import Any, Optional

import httpx

from .config import BenchmarkConfig, DEFAULT_CONFIG
from .metrics import BenchmarkResult, MetricsCollector, format_result_table


class APIBenchmark:
    """Benchmark API endpoint latency and throughput."""

    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.token: Optional[str] = None
        self.fleet_id: Optional[str] = None

    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Authenticate and get JWT token."""
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
                return True
            print(f"Auth failed: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            print(f"Auth error: {e}")
            return False

    async def get_or_create_fleet(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get or create a test fleet."""
        headers = {"Authorization": f"Bearer {self.token}"}

        # Try to get existing fleets
        try:
            response = await client.get(f"{self.config.url}/fleets", headers=headers)
            if response.status_code == 200:
                fleets = response.json()
                if fleets:
                    self.fleet_id = fleets[0]["id"]
                    return self.fleet_id
        except Exception:
            pass

        # Create new fleet
        try:
            response = await client.post(
                f"{self.config.url}/fleets",
                headers=headers,
                json={"name": "benchmark-fleet", "description": "Benchmark test fleet"},
            )
            if response.status_code in (200, 201):
                data = response.json()
                self.fleet_id = data.get("id")
                return self.fleet_id
        except Exception as e:
            print(f"Failed to create fleet: {e}")

        return None

    async def bench_endpoint(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        name: str,
        description: str,
        headers: Optional[dict] = None,
        json_body: Optional[dict] = None,
        data: Optional[dict] = None,
        concurrent: int = 10,
        duration: int = 30,
        warmup: int = 5,
    ) -> BenchmarkResult:
        """Benchmark a single endpoint."""
        collector = MetricsCollector(name)
        url = f"{self.config.url}{endpoint}"

        async def make_request() -> tuple[float, bool, Optional[str]]:
            """Make a single request and return latency, success, error."""
            start = time.perf_counter()
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(
                        url, headers=headers, json=json_body, data=data
                    )
                else:
                    return 0, False, f"Unsupported method: {method}"

                latency_ms = (time.perf_counter() - start) * 1000
                success = 200 <= response.status_code < 300
                error = None if success else f"{response.status_code}: {response.text[:100]}"
                return latency_ms, success, error
            except Exception as e:
                latency_ms = (time.perf_counter() - start) * 1000
                return latency_ms, False, str(e)

        async def worker(stop_event: asyncio.Event, record: bool = True) -> None:
            """Worker that continuously makes requests."""
            while not stop_event.is_set():
                latency_ms, success, error = await make_request()
                if record:
                    collector.record_request(latency_ms, success, error=error)
                await asyncio.sleep(0.001)  # Small delay to prevent tight loop

        # Warmup phase
        print(f"  Warming up ({warmup}s)...")
        warmup_stop = asyncio.Event()
        warmup_tasks = [
            asyncio.create_task(worker(warmup_stop, record=False))
            for _ in range(concurrent)
        ]
        await asyncio.sleep(warmup)
        warmup_stop.set()
        await asyncio.gather(*warmup_tasks, return_exceptions=True)

        # Benchmark phase
        print(f"  Running benchmark ({duration}s, {concurrent} clients)...")
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
            description=description,
            config={
                "concurrent_clients": concurrent,
                "duration_seconds": duration,
                "warmup_seconds": warmup,
                "endpoint": endpoint,
                "method": method,
            },
            thresholds={
                "p95_ms": self.config.latency_p95_threshold_ms,
                "p99_ms": self.config.latency_p99_threshold_ms,
                "max_error_rate": self.config.max_error_rate,
            },
        )

    async def run_all(self) -> list[BenchmarkResult]:
        """Run all API benchmarks."""
        results = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Authenticate
            print("\nAuthenticating...")
            if not await self.authenticate(client):
                print("Authentication failed, skipping authenticated benchmarks")
                auth_headers = None
            else:
                auth_headers = {"Authorization": f"Bearer {self.token}"}
                await self.get_or_create_fleet(client)

            # Health endpoint (no auth)
            print("\n[1/6] Benchmarking: GET /health")
            result = await self.bench_endpoint(
                client,
                method="GET",
                endpoint="/status/health",
                name="health_check",
                description="Health check endpoint - no auth, simple response",
                concurrent=self.config.concurrent_clients,
                duration=self.config.duration_seconds,
                warmup=self.config.warmup_seconds,
            )
            print(format_result_table(result))
            results.append(result)

            # Authentication endpoint
            print("\n[2/6] Benchmarking: POST /auth/token")
            result = await self.bench_endpoint(
                client,
                method="POST",
                endpoint="/auth/token",
                name="auth_token",
                description="Authentication - password validation, token generation",
                data={
                    "username": self.config.admin_email,
                    "password": self.config.admin_password,
                },
                concurrent=min(self.config.concurrent_clients, 20),  # Don't overload auth
                duration=self.config.duration_seconds,
                warmup=self.config.warmup_seconds,
            )
            print(format_result_table(result))
            results.append(result)

            if auth_headers:
                # List fleets
                print("\n[3/6] Benchmarking: GET /fleets")
                result = await self.bench_endpoint(
                    client,
                    method="GET",
                    endpoint="/fleets",
                    name="list_fleets",
                    description="List fleets - auth required, database query",
                    headers=auth_headers,
                    concurrent=self.config.concurrent_clients,
                    duration=self.config.duration_seconds,
                    warmup=self.config.warmup_seconds,
                )
                print(format_result_table(result))
                results.append(result)

                # Dashboard stats
                print("\n[4/6] Benchmarking: GET /dashboard/stats")
                result = await self.bench_endpoint(
                    client,
                    method="GET",
                    endpoint="/dashboard/stats",
                    name="dashboard_stats",
                    description="Dashboard statistics - complex aggregation",
                    headers=auth_headers,
                    concurrent=self.config.concurrent_clients,
                    duration=self.config.duration_seconds,
                    warmup=self.config.warmup_seconds,
                )
                print(format_result_table(result))
                results.append(result)

                # Telemetry pipeline
                print("\n[5/6] Benchmarking: GET /telemetry/pipeline")
                result = await self.bench_endpoint(
                    client,
                    method="GET",
                    endpoint="/telemetry/pipeline",
                    name="telemetry_pipeline",
                    description="Telemetry pipeline stats - time-range query",
                    headers=auth_headers,
                    concurrent=self.config.concurrent_clients,
                    duration=self.config.duration_seconds,
                    warmup=self.config.warmup_seconds,
                )
                print(format_result_table(result))
                results.append(result)

                # Identity inventory
                print("\n[6/6] Benchmarking: GET /identity/inventory")
                result = await self.bench_endpoint(
                    client,
                    method="GET",
                    endpoint="/identity/inventory",
                    name="identity_inventory",
                    description="Identity inventory - certificate listing",
                    headers=auth_headers,
                    concurrent=self.config.concurrent_clients,
                    duration=self.config.duration_seconds,
                    warmup=self.config.warmup_seconds,
                )
                print(format_result_table(result))
                results.append(result)

        return results


async def run_api_benchmarks(config: Optional[BenchmarkConfig] = None) -> list[BenchmarkResult]:
    """Entry point for API benchmarks."""
    benchmark = APIBenchmark(config)
    return await benchmark.run_all()


if __name__ == "__main__":
    import sys

    results = asyncio.run(run_api_benchmarks())

    # Summary
    print("\n" + "=" * 60)
    print("API BENCHMARK SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.name}: p95={result.latency.p95_ms:.1f}ms, rps={result.throughput.requests_per_second:.1f}")

    print(f"\nTotal: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
