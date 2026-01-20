"""
Benchmark Configuration

Configurable parameters for load testing and performance measurement.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    # Target server
    base_url: str = os.getenv("BENCH_BASE_URL", "http://localhost:8000")
    api_prefix: str = "/api/v1"

    # Authentication
    admin_email: str = os.getenv("BENCH_ADMIN_EMAIL", "admin@tensorguard.local")
    admin_password: str = os.getenv("BENCH_ADMIN_PASSWORD", "admin123")
    fleet_api_key: Optional[str] = os.getenv("BENCH_FLEET_API_KEY")

    # Load parameters
    concurrent_clients: int = int(os.getenv("BENCH_CONCURRENCY", "10"))
    duration_seconds: int = int(os.getenv("BENCH_DURATION", "30"))
    warmup_seconds: int = int(os.getenv("BENCH_WARMUP", "5"))
    cooldown_seconds: int = int(os.getenv("BENCH_COOLDOWN", "2"))

    # Telemetry ingest parameters
    batch_sizes: list = field(default_factory=lambda: [50, 100, 500, 1000])
    events_per_second_targets: list = field(default_factory=lambda: [100, 500, 1000, 5000])
    num_simulated_devices: int = int(os.getenv("BENCH_DEVICES", "100"))

    # Thresholds (for pass/fail)
    latency_p50_threshold_ms: float = float(os.getenv("BENCH_P50_THRESHOLD", "100"))
    latency_p95_threshold_ms: float = float(os.getenv("BENCH_P95_THRESHOLD", "500"))
    latency_p99_threshold_ms: float = float(os.getenv("BENCH_P99_THRESHOLD", "1000"))
    min_throughput_rps: float = float(os.getenv("BENCH_MIN_THROUGHPUT", "100"))
    max_error_rate: float = float(os.getenv("BENCH_MAX_ERROR_RATE", "0.01"))  # 1%

    # Resource thresholds
    max_cpu_percent: float = float(os.getenv("BENCH_MAX_CPU", "80"))
    max_memory_mb: float = float(os.getenv("BENCH_MAX_MEMORY", "2000"))

    # Output
    output_dir: str = os.getenv("BENCH_OUTPUT_DIR", "artifacts/benchmarks")
    save_raw_results: bool = True
    generate_plots: bool = True

    @property
    def url(self) -> str:
        """Full API URL."""
        return f"{self.base_url}{self.api_prefix}"


# Default configuration
DEFAULT_CONFIG = BenchmarkConfig()


# Test scenarios
SCENARIOS = {
    "smoke": {
        "description": "Quick smoke test",
        "concurrent_clients": 5,
        "duration_seconds": 10,
        "batch_sizes": [50],
        "events_per_second_targets": [100],
    },
    "standard": {
        "description": "Standard benchmark run",
        "concurrent_clients": 10,
        "duration_seconds": 30,
        "batch_sizes": [50, 100, 500],
        "events_per_second_targets": [100, 500, 1000],
    },
    "stress": {
        "description": "Stress test to find limits",
        "concurrent_clients": 50,
        "duration_seconds": 60,
        "batch_sizes": [100, 500, 1000],
        "events_per_second_targets": [1000, 5000, 10000],
    },
    "soak": {
        "description": "Extended stability test",
        "concurrent_clients": 20,
        "duration_seconds": 300,
        "batch_sizes": [100],
        "events_per_second_targets": [500],
    },
}
