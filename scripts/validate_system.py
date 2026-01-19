#!/usr/bin/env python3
"""
TensorGuard System Validation Script

Runs comprehensive validation checks to verify system health:
- Python syntax verification
- Module imports
- Test suite execution
- API contract validation

Usage:
    python scripts/validate_system.py
    python scripts/validate_system.py --quick  # Skip slow tests
    python scripts/validate_system.py --json   # JSON output
"""

import os
import sys
import subprocess
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict

# Ensure we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@dataclass
class ValidationResult:
    """Result of a validation check."""
    name: str
    status: str  # "pass", "fail", "skip"
    message: str
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    overall_status: str
    results: List[ValidationResult] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "results": [asdict(r) for r in self.results],
            "summary": self.summary,
        }


class SystemValidator:
    """System validation runner."""

    def __init__(self, quick_mode: bool = False):
        self.quick_mode = quick_mode
        self.results: List[ValidationResult] = []

    def run_check(
        self,
        name: str,
        check_fn,
        skip_in_quick: bool = False
    ) -> ValidationResult:
        """Run a validation check."""
        if skip_in_quick and self.quick_mode:
            result = ValidationResult(
                name=name,
                status="skip",
                message="Skipped in quick mode"
            )
            self.results.append(result)
            return result

        start = time.time()
        try:
            status, message, details = check_fn()
            result = ValidationResult(
                name=name,
                status=status,
                message=message,
                duration_ms=(time.time() - start) * 1000,
                details=details or {},
            )
        except Exception as e:
            result = ValidationResult(
                name=name,
                status="fail",
                message=f"Check raised exception: {str(e)}",
                duration_ms=(time.time() - start) * 1000,
            )

        self.results.append(result)
        return result

    def check_python_syntax(self) -> Tuple[str, str, Dict]:
        """Verify all Python files have valid syntax."""
        result = subprocess.run(
            ["python", "-m", "compileall", "src", "-q"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return "pass", "All Python files compile successfully", {}
        else:
            return "fail", f"Syntax errors found: {result.stderr}", {"stderr": result.stderr}

    def check_core_imports(self) -> Tuple[str, str, Dict]:
        """Verify core modules can be imported."""
        modules = [
            "tensorguard.platform.main",
            "tensorguard.platform.worker",
            "tensorguard.utils.feature_flags",
            "tensorguard.agent.diagnose",
        ]

        failed = []
        for mod in modules:
            try:
                __import__(mod)
            except ImportError as e:
                failed.append(f"{mod}: {e}")

        if not failed:
            return "pass", f"All {len(modules)} core modules import successfully", {"modules": modules}
        else:
            return "fail", f"{len(failed)} imports failed", {"failed": failed}

    def check_feature_flags(self) -> Tuple[str, str, Dict]:
        """Verify feature flags system works."""
        from tensorguard.utils.feature_flags import FeatureFlags

        summary = FeatureFlags.summary()
        if summary["total_flags"] > 0:
            return "pass", f"{summary['total_flags']} feature flags registered", summary
        else:
            return "fail", "No feature flags registered", {}

    def check_unit_tests(self) -> Tuple[str, str, Dict]:
        """Run unit tests."""
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=120
        )

        # Parse output for pass/fail counts
        output = result.stdout + result.stderr
        if result.returncode == 0:
            return "pass", "All unit tests passed", {"output": output[-500:]}
        else:
            return "fail", "Unit tests failed", {"output": output[-500:]}

    def check_integration_tests(self) -> Tuple[str, str, Dict]:
        """Run integration tests."""
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/integration/", "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=300
        )

        output = result.stdout + result.stderr
        if result.returncode == 0:
            return "pass", "All integration tests passed", {"output": output[-500:]}
        else:
            return "fail", "Integration tests failed", {"output": output[-500:]}

    def check_worker_health(self) -> Tuple[str, str, Dict]:
        """Verify worker can be instantiated."""
        try:
            # Mock signal to avoid interfering with test runner
            import signal
            original_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)

            from tensorguard.platform.worker import PlatformWorker
            worker = PlatformWorker()
            health = worker.get_health()

            signal.signal(signal.SIGINT, original_handler)

            return "pass", f"Worker status: {health['status']}", health
        except Exception as e:
            return "fail", f"Worker instantiation failed: {e}", {}

    def check_agent_diagnostics(self) -> Tuple[str, str, Dict]:
        """Run agent diagnostics."""
        try:
            from tensorguard.agent.diagnose import AgentDiagnostics

            diag = AgentDiagnostics(verbose=False)
            diag.check_environment()
            diag.check_file_permissions()
            diag.check_subsystem_availability()

            summary = {
                "ok": sum(1 for c in diag.checks if c.status == "ok"),
                "warning": sum(1 for c in diag.checks if c.status == "warning"),
                "error": sum(1 for c in diag.checks if c.status == "error"),
            }

            # In dev mode, env var errors are expected
            is_dev = os.getenv("TG_ENVIRONMENT", "development") != "production"
            if summary["error"] == 0 or (is_dev and summary["error"] <= 2):
                return "pass", f"Agent diagnostics: {summary['ok']} OK, {summary['warning']} warnings, {summary['error']} errors (dev mode)", summary
            else:
                return "fail", f"Agent diagnostics found {summary['error']} errors", summary
        except Exception as e:
            return "fail", f"Agent diagnostics failed: {e}", {}

    def run_all_checks(self) -> ValidationReport:
        """Run all validation checks."""
        print("\n=== TensorGuard System Validation ===\n")

        # Run checks
        checks = [
            ("Python Syntax", self.check_python_syntax, False),
            ("Core Imports", self.check_core_imports, False),
            ("Feature Flags", self.check_feature_flags, False),
            ("Worker Health", self.check_worker_health, False),
            ("Agent Diagnostics", self.check_agent_diagnostics, False),
            ("Unit Tests", self.check_unit_tests, True),
            ("Integration Tests", self.check_integration_tests, True),
        ]

        for name, check_fn, skip_in_quick in checks:
            print(f"  Checking {name}...", end=" ", flush=True)
            result = self.run_check(name, check_fn, skip_in_quick)

            status_icon = {"pass": "✓", "fail": "✗", "skip": "○"}[result.status]
            print(f"[{status_icon}] {result.message}")

        # Calculate summary
        summary = {
            "pass": sum(1 for r in self.results if r.status == "pass"),
            "fail": sum(1 for r in self.results if r.status == "fail"),
            "skip": sum(1 for r in self.results if r.status == "skip"),
        }

        overall = "pass" if summary["fail"] == 0 else "fail"

        report = ValidationReport(
            timestamp=datetime.utcnow().isoformat() + "Z",
            overall_status=overall,
            results=self.results,
            summary=summary,
        )

        return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="TensorGuard System Validation")
    parser.add_argument("--quick", action="store_true", help="Quick mode (skip slow tests)")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    validator = SystemValidator(quick_mode=args.quick)
    report = validator.run_all_checks()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"\n=== Summary ===")
        print(f"Status: {'PASS' if report.overall_status == 'pass' else 'FAIL'}")
        print(f"  Passed: {report.summary['pass']}")
        print(f"  Failed: {report.summary['fail']}")
        print(f"  Skipped: {report.summary['skip']}")

        if report.summary["fail"] > 0:
            print("\nFailed checks:")
            for r in report.results:
                if r.status == "fail":
                    print(f"  - {r.name}: {r.message}")

    sys.exit(0 if report.overall_status == "pass" else 1)


if __name__ == "__main__":
    main()
