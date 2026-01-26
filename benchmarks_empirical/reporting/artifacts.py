"""
Artifact Management for Empirical Benchmarks

Handles saving and loading of benchmark results, manifests, and raw data.
Integrates with TensorGuardFlow artifact management patterns.
"""

import json
import os
import sys
import platform
import subprocess
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class SystemInfo:
    """System information for reproducibility."""

    python_version: str
    platform: str
    platform_version: str
    cpu: str
    cpu_count: int
    ram_gb: float
    gpu_available: bool
    gpu_name: Optional[str]
    gpu_memory_gb: Optional[float]
    cuda_version: Optional[str]
    torch_version: Optional[str]

    @classmethod
    def collect(cls) -> "SystemInfo":
        """Collect current system information."""
        import platform as plat

        # CPU info
        try:
            if plat.system() == "Linux":
                cpu_info = subprocess.check_output(
                    "cat /proc/cpuinfo | grep 'model name' | head -1",
                    shell=True
                ).decode().strip().split(": ")[-1]
            else:
                cpu_info = plat.processor()
        except Exception:
            cpu_info = plat.processor()

        # RAM info
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        except ImportError:
            ram_gb = 0.0

        # GPU info
        gpu_available = False
        gpu_name = None
        gpu_memory_gb = None
        cuda_version = None

        if TORCH_AVAILABLE and torch.cuda.is_available():
            gpu_available = True
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            cuda_version = torch.version.cuda

        torch_version = torch.__version__ if TORCH_AVAILABLE else None

        return cls(
            python_version=sys.version,
            platform=plat.system(),
            platform_version=plat.version(),
            cpu=cpu_info,
            cpu_count=os.cpu_count() or 1,
            ram_gb=round(ram_gb, 2),
            gpu_available=gpu_available,
            gpu_name=gpu_name,
            gpu_memory_gb=round(gpu_memory_gb, 2) if gpu_memory_gb else None,
            cuda_version=cuda_version,
            torch_version=torch_version,
        )


@dataclass
class RunManifest:
    """
    Complete manifest for a benchmark run.

    Contains all information needed to reproduce the benchmark.
    """

    run_id: str
    timestamp: str
    git_commit: Optional[str]
    git_branch: Optional[str]
    git_dirty: bool
    system_info: Dict[str, Any]
    pip_freeze: List[str]
    suite: str
    config: Dict[str, Any]
    seeds: List[int]
    duration_seconds: float
    success: bool
    error_message: Optional[str]

    @classmethod
    def create(
        cls,
        suite: str,
        config: Dict[str, Any],
        seeds: List[int],
    ) -> "RunManifest":
        """Create a new run manifest."""
        # Generate run ID
        timestamp = datetime.now(timezone.utc).isoformat()
        run_id = hashlib.sha256(
            f"{timestamp}{suite}{seeds}".encode()
        ).hexdigest()[:12]

        # Get git info
        git_commit = None
        git_branch = None
        git_dirty = False

        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL
            ).decode().strip()

            git_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL
            ).decode().strip()

            status = subprocess.check_output(
                ["git", "status", "--porcelain"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            git_dirty = len(status) > 0
        except Exception:
            pass

        # Get pip freeze
        try:
            pip_freeze = subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"],
                stderr=subprocess.DEVNULL
            ).decode().strip().split("\n")
        except Exception:
            pip_freeze = []

        # Collect system info
        system_info = asdict(SystemInfo.collect())

        return cls(
            run_id=run_id,
            timestamp=timestamp,
            git_commit=git_commit,
            git_branch=git_branch,
            git_dirty=git_dirty,
            system_info=system_info,
            pip_freeze=pip_freeze,
            suite=suite,
            config=config,
            seeds=seeds,
            duration_seconds=0.0,
            success=False,
            error_message=None,
        )

    def finalize(self, duration: float, success: bool, error: Optional[str] = None):
        """Finalize the manifest after run completion."""
        self.duration_seconds = duration
        self.success = success
        self.error_message = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ArtifactManager:
    """
    Manages benchmark artifacts and outputs.

    Directory structure:
    reports/
    ├── run_manifest.json
    ├── metrics.json
    ├── benchmark_results.csv
    ├── benchmark_report.md
    └── raw/
        ├── clvision/
        │   ├── seed_42/
        │   │   ├── accuracy_matrix.npy
        │   │   └── ...
        │   └── ...
        ├── wilds/
        └── peft/
    """

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.raw_dir = self.output_dir / "raw"

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def get_raw_dir(self, suite: str, seed: int) -> Path:
        """Get raw artifact directory for a suite and seed."""
        raw_path = self.raw_dir / suite / f"seed_{seed}"
        raw_path.mkdir(parents=True, exist_ok=True)
        return raw_path

    def save_manifest(self, manifest: RunManifest):
        """Save run manifest."""
        path = self.output_dir / "run_manifest.json"
        with open(path, 'w') as f:
            json.dump(manifest.to_dict(), f, indent=2)
        print(f"[Artifacts] Saved manifest: {path}")

    def save_metrics(self, metrics: Dict[str, Any]):
        """Save aggregated metrics."""
        path = self.output_dir / "metrics.json"
        with open(path, 'w') as f:
            json.dump(metrics, f, indent=2, default=self._json_serializer)
        print(f"[Artifacts] Saved metrics: {path}")

    def save_results_csv(self, results: List[Dict[str, Any]]):
        """Save results as CSV."""
        import csv

        if not results:
            return

        path = self.output_dir / "benchmark_results.csv"

        # First pass: flatten all rows and collect all fieldnames
        all_fieldnames = set()
        flat_rows = []

        for row in results:
            flat_row = {}
            for k, v in row.items():
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        flat_row[f"{k}_{k2}"] = v2
                elif isinstance(v, (list, np.ndarray)):
                    flat_row[k] = str(v)
                else:
                    flat_row[k] = v
            flat_rows.append(flat_row)
            all_fieldnames.update(flat_row.keys())

        # Sort fieldnames for consistent ordering
        fieldnames = sorted(list(all_fieldnames))

        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for flat_row in flat_rows:
                writer.writerow(flat_row)

        print(f"[Artifacts] Saved CSV: {path}")

    def save_raw_artifact(
        self,
        suite: str,
        seed: int,
        name: str,
        data: Any,
    ):
        """Save a raw artifact."""
        raw_dir = self.get_raw_dir(suite, seed)

        if isinstance(data, np.ndarray):
            path = raw_dir / f"{name}.npy"
            np.save(path, data)
        elif isinstance(data, dict):
            path = raw_dir / f"{name}.json"
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, default=self._json_serializer)
        elif TORCH_AVAILABLE and isinstance(data, torch.Tensor):
            path = raw_dir / f"{name}.pt"
            torch.save(data, path)
        else:
            path = raw_dir / f"{name}.json"
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, default=self._json_serializer)

    def save_model_checkpoint(
        self,
        suite: str,
        seed: int,
        task_id: int,
        model_state: Dict,
        method: str,
    ):
        """Save model checkpoint."""
        raw_dir = self.get_raw_dir(suite, seed)
        path = raw_dir / f"checkpoint_{method}_task{task_id}.pt"
        torch.save(model_state, path)

    def load_manifest(self) -> Optional[RunManifest]:
        """Load existing manifest."""
        path = self.output_dir / "run_manifest.json"
        if not path.exists():
            return None
        with open(path, 'r') as f:
            data = json.load(f)
        return RunManifest(**data)

    def load_metrics(self) -> Optional[Dict[str, Any]]:
        """Load existing metrics."""
        path = self.output_dir / "metrics.json"
        if not path.exists():
            return None
        with open(path, 'r') as f:
            return json.load(f)

    def _json_serializer(self, obj):
        """Custom JSON serializer for numpy/torch types."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        if TORCH_AVAILABLE and isinstance(obj, torch.Tensor):
            return obj.cpu().numpy().tolist()
        if isinstance(obj, Path):
            return str(obj)
        return str(obj)

    def verify_outputs_exist(self) -> bool:
        """Verify that all required outputs exist."""
        required = [
            self.output_dir / "run_manifest.json",
            self.output_dir / "metrics.json",
            self.output_dir / "benchmark_results.csv",
            self.output_dir / "benchmark_report.md",
        ]

        missing = [p for p in required if not p.exists()]
        if missing:
            print(f"[Artifacts] Missing outputs: {missing}")
            return False

        # Verify non-empty
        for p in required:
            if p.stat().st_size == 0:
                print(f"[Artifacts] Empty file: {p}")
                return False

        return True
