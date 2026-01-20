"""
Metrics Collection and Analysis

Utilities for collecting, aggregating, and analyzing benchmark metrics.
"""

import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class LatencyStats:
    """Latency statistics for a benchmark run."""

    count: int = 0
    min_ms: float = float("inf")
    max_ms: float = 0
    mean_ms: float = 0
    median_ms: float = 0
    p50_ms: float = 0
    p90_ms: float = 0
    p95_ms: float = 0
    p99_ms: float = 0
    std_dev_ms: float = 0

    @classmethod
    def from_samples(cls, samples_ms: list[float]) -> "LatencyStats":
        """Calculate statistics from latency samples."""
        if not samples_ms:
            return cls()

        sorted_samples = sorted(samples_ms)
        n = len(sorted_samples)

        return cls(
            count=n,
            min_ms=min(sorted_samples),
            max_ms=max(sorted_samples),
            mean_ms=statistics.mean(sorted_samples),
            median_ms=statistics.median(sorted_samples),
            p50_ms=sorted_samples[int(n * 0.50)] if n > 0 else 0,
            p90_ms=sorted_samples[int(n * 0.90)] if n > 1 else sorted_samples[-1],
            p95_ms=sorted_samples[int(n * 0.95)] if n > 1 else sorted_samples[-1],
            p99_ms=sorted_samples[int(n * 0.99)] if n > 1 else sorted_samples[-1],
            std_dev_ms=statistics.stdev(sorted_samples) if n > 1 else 0,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "count": self.count,
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "mean_ms": round(self.mean_ms, 3),
            "median_ms": round(self.median_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p90_ms": round(self.p90_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "std_dev_ms": round(self.std_dev_ms, 3),
        }


@dataclass
class ThroughputStats:
    """Throughput statistics for a benchmark run."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    duration_seconds: float = 0
    requests_per_second: float = 0
    events_per_second: float = 0  # For telemetry ingest
    error_rate: float = 0
    total_bytes: int = 0
    bytes_per_second: float = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "duration_seconds": round(self.duration_seconds, 3),
            "requests_per_second": round(self.requests_per_second, 3),
            "events_per_second": round(self.events_per_second, 3),
            "error_rate": round(self.error_rate, 5),
            "total_bytes": self.total_bytes,
            "bytes_per_second": round(self.bytes_per_second, 3),
        }


@dataclass
class ResourceStats:
    """Resource utilization statistics."""

    cpu_percent_mean: float = 0
    cpu_percent_max: float = 0
    memory_mb_mean: float = 0
    memory_mb_max: float = 0
    disk_read_mb: float = 0
    disk_write_mb: float = 0
    network_recv_mb: float = 0
    network_sent_mb: float = 0
    db_connections_mean: float = 0
    db_connections_max: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cpu_percent_mean": round(self.cpu_percent_mean, 2),
            "cpu_percent_max": round(self.cpu_percent_max, 2),
            "memory_mb_mean": round(self.memory_mb_mean, 2),
            "memory_mb_max": round(self.memory_mb_max, 2),
            "disk_read_mb": round(self.disk_read_mb, 2),
            "disk_write_mb": round(self.disk_write_mb, 2),
            "network_recv_mb": round(self.network_recv_mb, 2),
            "network_sent_mb": round(self.network_sent_mb, 2),
            "db_connections_mean": round(self.db_connections_mean, 2),
            "db_connections_max": self.db_connections_max,
        }


@dataclass
class BenchmarkResult:
    """Complete benchmark result for a single test."""

    name: str
    description: str
    started_at: str = ""
    ended_at: str = ""
    duration_seconds: float = 0
    config: dict = field(default_factory=dict)
    latency: LatencyStats = field(default_factory=LatencyStats)
    throughput: ThroughputStats = field(default_factory=ThroughputStats)
    resources: ResourceStats = field(default_factory=ResourceStats)
    passed: bool = True
    failure_reasons: list = field(default_factory=list)
    raw_samples: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "config": self.config,
            "latency": self.latency.to_dict(),
            "throughput": self.throughput.to_dict(),
            "resources": self.resources.to_dict(),
            "passed": self.passed,
            "failure_reasons": self.failure_reasons,
            "error_count": len(self.errors),
        }

    def save(self, output_dir: str) -> str:
        """Save result to JSON file."""
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.name}_{timestamp}.json"
        filepath = path / filename

        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        return str(filepath)


class MetricsCollector:
    """Collects and aggregates metrics during benchmark runs."""

    def __init__(self, name: str):
        self.name = name
        self.latency_samples: list[float] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.successful: int = 0
        self.failed: int = 0
        self.total_events: int = 0
        self.total_bytes: int = 0
        self.errors: list[str] = []
        self.cpu_samples: list[float] = []
        self.memory_samples: list[float] = []

    def start(self) -> None:
        """Mark the start of the benchmark."""
        self.start_time = time.time()

    def stop(self) -> None:
        """Mark the end of the benchmark."""
        self.end_time = time.time()

    def record_request(
        self,
        latency_ms: float,
        success: bool,
        events: int = 1,
        bytes_sent: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Record a single request result."""
        self.latency_samples.append(latency_ms)
        if success:
            self.successful += 1
        else:
            self.failed += 1
            if error:
                self.errors.append(error)
        self.total_events += events
        self.total_bytes += bytes_sent

    def record_resources(self, cpu_percent: float, memory_mb: float) -> None:
        """Record resource utilization sample."""
        self.cpu_samples.append(cpu_percent)
        self.memory_samples.append(memory_mb)

    def get_result(
        self,
        description: str = "",
        config: Optional[dict] = None,
        thresholds: Optional[dict] = None,
    ) -> BenchmarkResult:
        """Calculate and return the benchmark result."""
        duration = (self.end_time or time.time()) - (self.start_time or time.time())

        latency_stats = LatencyStats.from_samples(self.latency_samples)

        total_requests = self.successful + self.failed
        throughput_stats = ThroughputStats(
            total_requests=total_requests,
            successful_requests=self.successful,
            failed_requests=self.failed,
            duration_seconds=duration,
            requests_per_second=total_requests / duration if duration > 0 else 0,
            events_per_second=self.total_events / duration if duration > 0 else 0,
            error_rate=self.failed / total_requests if total_requests > 0 else 0,
            total_bytes=self.total_bytes,
            bytes_per_second=self.total_bytes / duration if duration > 0 else 0,
        )

        resource_stats = ResourceStats(
            cpu_percent_mean=(
                statistics.mean(self.cpu_samples) if self.cpu_samples else 0
            ),
            cpu_percent_max=max(self.cpu_samples) if self.cpu_samples else 0,
            memory_mb_mean=(
                statistics.mean(self.memory_samples) if self.memory_samples else 0
            ),
            memory_mb_max=max(self.memory_samples) if self.memory_samples else 0,
        )

        # Check thresholds
        passed = True
        failure_reasons = []

        if thresholds:
            if latency_stats.p95_ms > thresholds.get("p95_ms", float("inf")):
                passed = False
                failure_reasons.append(
                    f"p95 latency {latency_stats.p95_ms:.1f}ms > {thresholds['p95_ms']}ms threshold"
                )

            if latency_stats.p99_ms > thresholds.get("p99_ms", float("inf")):
                passed = False
                failure_reasons.append(
                    f"p99 latency {latency_stats.p99_ms:.1f}ms > {thresholds['p99_ms']}ms threshold"
                )

            if throughput_stats.requests_per_second < thresholds.get("min_rps", 0):
                passed = False
                failure_reasons.append(
                    f"Throughput {throughput_stats.requests_per_second:.1f} rps < {thresholds['min_rps']} rps threshold"
                )

            if throughput_stats.error_rate > thresholds.get("max_error_rate", 1.0):
                passed = False
                failure_reasons.append(
                    f"Error rate {throughput_stats.error_rate:.2%} > {thresholds['max_error_rate']:.2%} threshold"
                )

        return BenchmarkResult(
            name=self.name,
            description=description,
            started_at=(
                datetime.fromtimestamp(self.start_time).isoformat()
                if self.start_time
                else ""
            ),
            ended_at=(
                datetime.fromtimestamp(self.end_time).isoformat()
                if self.end_time
                else ""
            ),
            duration_seconds=duration,
            config=config or {},
            latency=latency_stats,
            throughput=throughput_stats,
            resources=resource_stats,
            passed=passed,
            failure_reasons=failure_reasons,
            raw_samples=self.latency_samples if len(self.latency_samples) < 10000 else [],
            errors=self.errors[:100],  # Limit error samples
        )


def format_result_table(result: BenchmarkResult) -> str:
    """Format a result as a text table for console output."""
    lines = [
        f"\n{'=' * 60}",
        f"Benchmark: {result.name}",
        f"{'=' * 60}",
        f"Status: {'PASSED' if result.passed else 'FAILED'}",
        f"Duration: {result.duration_seconds:.1f}s",
        "",
        "Latency (ms):",
        f"  p50:    {result.latency.p50_ms:>8.2f}",
        f"  p95:    {result.latency.p95_ms:>8.2f}",
        f"  p99:    {result.latency.p99_ms:>8.2f}",
        f"  max:    {result.latency.max_ms:>8.2f}",
        "",
        "Throughput:",
        f"  Requests:     {result.throughput.total_requests:>8}",
        f"  RPS:          {result.throughput.requests_per_second:>8.1f}",
        f"  Events/s:     {result.throughput.events_per_second:>8.1f}",
        f"  Error Rate:   {result.throughput.error_rate:>8.2%}",
        "",
    ]

    if result.resources.cpu_percent_max > 0:
        lines.extend(
            [
                "Resources:",
                f"  CPU (max):    {result.resources.cpu_percent_max:>8.1f}%",
                f"  Memory (max): {result.resources.memory_mb_max:>8.1f} MB",
                "",
            ]
        )

    if not result.passed:
        lines.extend(
            [
                "Failures:",
                *[f"  - {r}" for r in result.failure_reasons],
                "",
            ]
        )

    lines.append("=" * 60)
    return "\n".join(lines)
