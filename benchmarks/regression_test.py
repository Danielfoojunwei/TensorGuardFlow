#!/usr/bin/env python3
"""
Performance Regression Test

Compares current benchmark results against a baseline to detect regressions.
Fails if p95 latency or throughput degrades beyond threshold.

Usage:
    python -m benchmarks.regression_test --baseline artifacts/benchmarks/baseline.json
    python -m benchmarks.regression_test --baseline artifacts/benchmarks/baseline.json --threshold 20
"""

import argparse
import json
import sys
from pathlib import Path


def load_results(path: str) -> dict:
    """Load benchmark results from JSON file."""
    with open(path) as f:
        return json.load(f)


def compare_results(
    baseline: dict,
    current: dict,
    latency_threshold_percent: float = 20.0,
    throughput_threshold_percent: float = 20.0,
) -> tuple[bool, list[str]]:
    """
    Compare current results against baseline.

    Returns:
        (passed, list of failure messages)
    """
    failures = []

    baseline_results = {r["name"]: r for r in baseline.get("results", [])}
    current_results = {r["name"]: r for r in current.get("results", [])}

    for name, current_result in current_results.items():
        if name not in baseline_results:
            continue

        baseline_result = baseline_results[name]

        # Compare p95 latency
        baseline_p95 = baseline_result.get("latency", {}).get("p95_ms", 0)
        current_p95 = current_result.get("latency", {}).get("p95_ms", 0)

        if baseline_p95 > 0:
            latency_change = ((current_p95 - baseline_p95) / baseline_p95) * 100
            if latency_change > latency_threshold_percent:
                failures.append(
                    f"REGRESSION: {name} p95 latency increased by {latency_change:.1f}% "
                    f"({baseline_p95:.1f}ms -> {current_p95:.1f}ms)"
                )

        # Compare throughput (RPS or events/s)
        baseline_rps = baseline_result.get("throughput", {}).get("requests_per_second", 0)
        current_rps = current_result.get("throughput", {}).get("requests_per_second", 0)

        if baseline_rps > 0:
            throughput_change = ((baseline_rps - current_rps) / baseline_rps) * 100
            if throughput_change > throughput_threshold_percent:
                failures.append(
                    f"REGRESSION: {name} throughput decreased by {throughput_change:.1f}% "
                    f"({baseline_rps:.1f} rps -> {current_rps:.1f} rps)"
                )

        # Compare events/s for ingest benchmarks
        baseline_eps = baseline_result.get("throughput", {}).get("events_per_second", 0)
        current_eps = current_result.get("throughput", {}).get("events_per_second", 0)

        if baseline_eps > 0:
            eps_change = ((baseline_eps - current_eps) / baseline_eps) * 100
            if eps_change > throughput_threshold_percent:
                failures.append(
                    f"REGRESSION: {name} event throughput decreased by {eps_change:.1f}% "
                    f"({baseline_eps:.1f} events/s -> {current_eps:.1f} events/s)"
                )

        # Compare error rate
        baseline_err = baseline_result.get("throughput", {}).get("error_rate", 0)
        current_err = current_result.get("throughput", {}).get("error_rate", 0)

        # Error rate increase of more than 1% is a regression
        if current_err > baseline_err + 0.01:
            failures.append(
                f"REGRESSION: {name} error rate increased "
                f"({baseline_err:.2%} -> {current_err:.2%})"
            )

    return len(failures) == 0, failures


def main():
    parser = argparse.ArgumentParser(
        description="Performance Regression Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Path to baseline benchmark results JSON",
    )
    parser.add_argument(
        "--current",
        help="Path to current benchmark results JSON (default: latest in artifacts/benchmarks)",
    )
    parser.add_argument(
        "--latency-threshold",
        type=float,
        default=20.0,
        help="Latency regression threshold in percent (default: 20%%)",
    )
    parser.add_argument(
        "--throughput-threshold",
        type=float,
        default=20.0,
        help="Throughput regression threshold in percent (default: 20%%)",
    )
    parser.add_argument(
        "--output",
        help="Path to save comparison report",
    )

    args = parser.parse_args()

    # Load baseline
    if not Path(args.baseline).exists():
        print(f"ERROR: Baseline file not found: {args.baseline}")
        sys.exit(1)

    baseline = load_results(args.baseline)
    print(f"Loaded baseline: {args.baseline}")

    # Find or load current results
    if args.current:
        current_path = args.current
    else:
        # Find latest benchmark file
        benchmark_dir = Path("artifacts/benchmarks")
        if not benchmark_dir.exists():
            print("ERROR: No benchmark results found in artifacts/benchmarks/")
            sys.exit(1)

        files = sorted(benchmark_dir.glob("benchmark_*.json"), reverse=True)
        if not files:
            print("ERROR: No benchmark result files found")
            sys.exit(1)

        current_path = str(files[0])

    if not Path(current_path).exists():
        print(f"ERROR: Current results file not found: {current_path}")
        sys.exit(1)

    current = load_results(current_path)
    print(f"Loaded current: {current_path}")

    # Compare
    print("\n" + "=" * 60)
    print("PERFORMANCE REGRESSION TEST")
    print("=" * 60)
    print(f"Latency threshold: {args.latency_threshold}%")
    print(f"Throughput threshold: {args.throughput_threshold}%")
    print()

    passed, failures = compare_results(
        baseline,
        current,
        latency_threshold_percent=args.latency_threshold,
        throughput_threshold_percent=args.throughput_threshold,
    )

    # Print comparison
    print("Benchmark Comparison:")
    print("-" * 60)

    baseline_results = {r["name"]: r for r in baseline.get("results", [])}
    current_results = {r["name"]: r for r in current.get("results", [])}

    for name, current_result in current_results.items():
        if name not in baseline_results:
            print(f"  {name}: NEW (no baseline)")
            continue

        baseline_result = baseline_results[name]

        baseline_p95 = baseline_result.get("latency", {}).get("p95_ms", 0)
        current_p95 = current_result.get("latency", {}).get("p95_ms", 0)
        baseline_rps = baseline_result.get("throughput", {}).get("requests_per_second", 0)
        current_rps = current_result.get("throughput", {}).get("requests_per_second", 0)

        p95_delta = ((current_p95 - baseline_p95) / baseline_p95 * 100) if baseline_p95 > 0 else 0
        rps_delta = ((current_rps - baseline_rps) / baseline_rps * 100) if baseline_rps > 0 else 0

        p95_sign = "+" if p95_delta > 0 else ""
        rps_sign = "+" if rps_delta > 0 else ""

        print(
            f"  {name}: p95={current_p95:.1f}ms ({p95_sign}{p95_delta:.1f}%), "
            f"rps={current_rps:.1f} ({rps_sign}{rps_delta:.1f}%)"
        )

    print()

    # Report result
    if passed:
        print("=" * 60)
        print("RESULT: PASSED - No performance regressions detected")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("RESULT: FAILED - Performance regressions detected")
        print("=" * 60)
        print()
        for failure in failures:
            print(f"  {failure}")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
