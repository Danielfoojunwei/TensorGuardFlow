#!/usr/bin/env python3
"""
TensorGuardFlow Benchmark Runner

Main CLI for running performance benchmarks.

Usage:
    python -m benchmarks.runner --help
    python -m benchmarks.runner api --duration 30 --concurrent 10
    python -m benchmarks.runner ingest --batch-size 100
    python -m benchmarks.runner all --scenario standard
"""

import argparse
import asyncio
import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.config import BenchmarkConfig, SCENARIOS
from benchmarks.metrics import BenchmarkResult


def get_system_info() -> dict:
    """Collect system information for the report."""
    try:
        import psutil

        cpu_count = psutil.cpu_count()
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
    except ImportError:
        cpu_count = os.cpu_count()
        memory_total_gb = 0

    return {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "processor": platform.processor() or "Unknown",
        "cpu_count": cpu_count,
        "memory_total_gb": round(memory_total_gb, 2),
    }


def save_results(results: list[BenchmarkResult], output_dir: str, prefix: str) -> str:
    """Save benchmark results to JSON file."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.json"
    filepath = path / filename

    output = {
        "system_info": get_system_info(),
        "results": [r.to_dict() for r in results],
        "summary": {
            "total_benchmarks": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
        },
    }

    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {filepath}")
    return str(filepath)


async def run_api_benchmarks(config: BenchmarkConfig) -> list[BenchmarkResult]:
    """Run API benchmarks."""
    from benchmarks.api_bench import run_api_benchmarks as _run

    return await _run(config)


async def run_ingest_benchmarks(config: BenchmarkConfig) -> list[BenchmarkResult]:
    """Run ingest benchmarks."""
    from benchmarks.ingest_bench import run_ingest_benchmarks as _run

    return await _run(config)


async def run_all_benchmarks(config: BenchmarkConfig) -> list[BenchmarkResult]:
    """Run all benchmarks."""
    results = []

    print("\n" + "=" * 60)
    print("RUNNING ALL BENCHMARKS")
    print("=" * 60)

    # API benchmarks
    print("\n>>> API Latency Benchmarks")
    api_results = await run_api_benchmarks(config)
    results.extend(api_results)

    # Ingest benchmarks
    print("\n>>> Telemetry Ingest Benchmarks")
    ingest_results = await run_ingest_benchmarks(config)
    results.extend(ingest_results)

    return results


def print_summary(results: list[BenchmarkResult]) -> None:
    """Print summary of all benchmark results."""
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    # Group by category
    api_results = [r for r in results if not r.name.startswith("ingest")]
    ingest_results = [r for r in results if r.name.startswith("ingest")]

    if api_results:
        print("\nAPI Benchmarks:")
        for result in api_results:
            status = "PASS" if result.passed else "FAIL"
            print(
                f"  [{status}] {result.name}: "
                f"p50={result.latency.p50_ms:.1f}ms, "
                f"p95={result.latency.p95_ms:.1f}ms, "
                f"rps={result.throughput.requests_per_second:.1f}"
            )

    if ingest_results:
        print("\nIngest Benchmarks:")
        for result in ingest_results:
            status = "PASS" if result.passed else "FAIL"
            print(
                f"  [{status}] {result.name}: "
                f"p50={result.latency.p50_ms:.1f}ms, "
                f"p95={result.latency.p95_ms:.1f}ms, "
                f"events/s={result.throughput.events_per_second:.1f}"
            )

    print(f"\n{'=' * 60}")
    print(f"Total: {passed} passed, {failed} failed")

    if failed > 0:
        print("\nFailures:")
        for result in results:
            if not result.passed:
                print(f"  {result.name}:")
                for reason in result.failure_reasons:
                    print(f"    - {reason}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="TensorGuardFlow Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m benchmarks.runner api
  python -m benchmarks.runner ingest --batch-size 100
  python -m benchmarks.runner all --scenario stress
  python -m benchmarks.runner all --duration 60 --concurrent 20
        """,
    )

    parser.add_argument(
        "command",
        choices=["api", "ingest", "all"],
        help="Benchmark type to run",
    )

    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the TensorGuardFlow API (default: http://localhost:8000)",
    )

    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        help="Predefined scenario to run",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration of each benchmark in seconds (default: 30)",
    )

    parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="Number of concurrent clients (default: 10)",
    )

    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Warmup period in seconds (default: 5)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        nargs="+",
        default=[50, 100, 500],
        help="Batch sizes for ingest tests (default: 50 100 500)",
    )

    parser.add_argument(
        "--devices",
        type=int,
        default=100,
        help="Number of simulated devices (default: 100)",
    )

    parser.add_argument(
        "--output-dir",
        default="artifacts/benchmarks",
        help="Output directory for results (default: artifacts/benchmarks)",
    )

    parser.add_argument(
        "--p95-threshold",
        type=float,
        default=500,
        help="p95 latency threshold in ms (default: 500)",
    )

    parser.add_argument(
        "--p99-threshold",
        type=float,
        default=1000,
        help="p99 latency threshold in ms (default: 1000)",
    )

    parser.add_argument(
        "--min-throughput",
        type=float,
        default=100,
        help="Minimum throughput threshold in rps (default: 100)",
    )

    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=0.01,
        help="Maximum error rate (default: 0.01 = 1%%)",
    )

    parser.add_argument(
        "--admin-email",
        default="admin@tensorguard.local",
        help="Admin email for authentication",
    )

    parser.add_argument(
        "--admin-password",
        default="admin123",
        help="Admin password for authentication",
    )

    args = parser.parse_args()

    # Build configuration
    config = BenchmarkConfig(
        base_url=args.base_url,
        admin_email=args.admin_email,
        admin_password=args.admin_password,
        concurrent_clients=args.concurrent,
        duration_seconds=args.duration,
        warmup_seconds=args.warmup,
        batch_sizes=args.batch_size,
        num_simulated_devices=args.devices,
        latency_p95_threshold_ms=args.p95_threshold,
        latency_p99_threshold_ms=args.p99_threshold,
        min_throughput_rps=args.min_throughput,
        max_error_rate=args.max_error_rate,
        output_dir=args.output_dir,
    )

    # Apply scenario overrides
    if args.scenario:
        scenario = SCENARIOS[args.scenario]
        print(f"\nUsing scenario: {args.scenario} - {scenario['description']}")
        config.concurrent_clients = scenario.get(
            "concurrent_clients", config.concurrent_clients
        )
        config.duration_seconds = scenario.get(
            "duration_seconds", config.duration_seconds
        )
        config.batch_sizes = scenario.get("batch_sizes", config.batch_sizes)

    # Print system info
    system_info = get_system_info()
    print("\n" + "=" * 60)
    print("TENSORGUARDFLOW BENCHMARK RUNNER")
    print("=" * 60)
    print(f"Target:     {config.base_url}")
    print(f"Platform:   {system_info['platform']} ({system_info['platform_version'][:50]}...)")
    print(f"Python:     {system_info['python_version']}")
    print(f"CPUs:       {system_info['cpu_count']}")
    print(f"Memory:     {system_info['memory_total_gb']} GB")
    print(f"Concurrent: {config.concurrent_clients}")
    print(f"Duration:   {config.duration_seconds}s per benchmark")
    print("=" * 60)

    # Run benchmarks
    try:
        if args.command == "api":
            results = asyncio.run(run_api_benchmarks(config))
        elif args.command == "ingest":
            results = asyncio.run(run_ingest_benchmarks(config))
        else:  # all
            results = asyncio.run(run_all_benchmarks(config))
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        sys.exit(1)

    # Print summary
    print_summary(results)

    # Save results
    prefix = f"benchmark_{args.command}"
    save_results(results, config.output_dir, prefix)

    # Exit with appropriate code
    failed = sum(1 for r in results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
