"""
Agent Diagnose Mode

Provides comprehensive diagnostic information about the agent's health,
connectivity, and configuration.

Usage:
    python -m tensorguard.agent.diagnose
    python -m tensorguard.agent.diagnose --verbose
    python -m tensorguard.agent.diagnose --json

Or from within agent code:
    from tensorguard.agent.diagnose import AgentDiagnostics
    diag = AgentDiagnostics()
    report = diag.run_full_diagnosis()
"""

import os
import sys
import json
import socket
import ssl
import time
import platform
import logging
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticCheck:
    """Result of a single diagnostic check."""
    name: str
    status: str  # "ok", "warning", "error", "skipped"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosticReport:
    """Complete diagnostic report."""
    timestamp: str
    agent_version: str
    overall_status: str  # "healthy", "degraded", "unhealthy"
    checks: List[DiagnosticCheck] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "agent_version": self.agent_version,
            "overall_status": self.overall_status,
            "checks": [c.to_dict() for c in self.checks],
            "environment": self.environment,
            "summary": self.summary,
        }


class AgentDiagnostics:
    """
    Comprehensive agent diagnostic tool.

    Checks:
    - Environment configuration
    - Control plane connectivity
    - TLS/certificate validity
    - File system permissions
    - Subsystem availability
    - Resource usage
    """

    VERSION = "1.0.0"

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.checks: List[DiagnosticCheck] = []

    def _add_check(
        self,
        name: str,
        status: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: float = 0.0
    ) -> DiagnosticCheck:
        """Add a diagnostic check result."""
        check = DiagnosticCheck(
            name=name,
            status=status,
            message=message,
            details=details or {},
            duration_ms=duration_ms,
        )
        self.checks.append(check)
        if self.verbose:
            status_icon = {"ok": "✓", "warning": "⚠", "error": "✗", "skipped": "○"}.get(status, "?")
            print(f"  [{status_icon}] {name}: {message}")
        return check

    def check_environment(self) -> None:
        """Check environment variables and configuration."""
        start = time.time()

        required_vars = {
            "TG_FLEET_API_KEY": "Fleet API key for authentication",
            "TG_FLEET_ID": "Fleet identifier",
        }

        optional_vars = {
            "TG_CONTROL_PLANE_URL": "Control plane URL (default: http://localhost:8000)",
            "TG_AGENT_NAME": "Agent name (default: hostname)",
            "TG_DATA_DIR": "Data storage directory",
        }

        missing = []
        present = []

        for var, desc in required_vars.items():
            if os.environ.get(var):
                present.append(var)
            else:
                missing.append(var)

        if missing:
            self._add_check(
                "environment_required",
                "error",
                f"Missing required variables: {', '.join(missing)}",
                {"missing": missing, "present": present},
                (time.time() - start) * 1000
            )
        else:
            self._add_check(
                "environment_required",
                "ok",
                "All required environment variables set",
                {"present": present},
                (time.time() - start) * 1000
            )

        # Check optional vars
        optional_present = [v for v in optional_vars if os.environ.get(v)]
        self._add_check(
            "environment_optional",
            "ok",
            f"{len(optional_present)}/{len(optional_vars)} optional variables set",
            {"present": optional_present},
            0
        )

    def check_control_plane_connectivity(self) -> None:
        """Check connectivity to control plane."""
        start = time.time()

        control_plane_url = os.environ.get("TG_CONTROL_PLANE_URL", "http://localhost:8000")

        try:
            parsed = urlparse(control_plane_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)

            # TCP connectivity check
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                self._add_check(
                    "control_plane_tcp",
                    "ok",
                    f"TCP connection to {host}:{port} successful",
                    {"host": host, "port": port},
                    (time.time() - start) * 1000
                )
            else:
                self._add_check(
                    "control_plane_tcp",
                    "error",
                    f"Cannot connect to {host}:{port}",
                    {"host": host, "port": port, "error_code": result},
                    (time.time() - start) * 1000
                )
                return

            # HTTP health check
            self._check_http_health(control_plane_url)

        except Exception as e:
            self._add_check(
                "control_plane_tcp",
                "error",
                f"Connection error: {str(e)}",
                {"url": control_plane_url, "error": str(e)},
                (time.time() - start) * 1000
            )

    def _check_http_health(self, base_url: str) -> None:
        """Check HTTP health endpoint."""
        start = time.time()

        try:
            import urllib.request
            import urllib.error

            health_url = f"{base_url}/health"
            req = urllib.request.Request(health_url, method='GET')
            req.add_header('User-Agent', 'TensorGuard-Agent-Diagnostics/1.0')

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    status_code = response.status
                    if status_code == 200:
                        self._add_check(
                            "control_plane_health",
                            "ok",
                            "Health endpoint responding",
                            {"url": health_url, "status": status_code},
                            (time.time() - start) * 1000
                        )
                    else:
                        self._add_check(
                            "control_plane_health",
                            "warning",
                            f"Health endpoint returned {status_code}",
                            {"url": health_url, "status": status_code},
                            (time.time() - start) * 1000
                        )
            except urllib.error.HTTPError as e:
                self._add_check(
                    "control_plane_health",
                    "warning",
                    f"Health endpoint returned {e.code}",
                    {"url": health_url, "status": e.code},
                    (time.time() - start) * 1000
                )
            except urllib.error.URLError as e:
                self._add_check(
                    "control_plane_health",
                    "error",
                    f"Cannot reach health endpoint: {e.reason}",
                    {"url": health_url, "error": str(e.reason)},
                    (time.time() - start) * 1000
                )

        except Exception as e:
            self._add_check(
                "control_plane_health",
                "error",
                f"Health check error: {str(e)}",
                {"error": str(e)},
                (time.time() - start) * 1000
            )

    def check_tls_certificates(self) -> None:
        """Check TLS certificate validity."""
        start = time.time()

        control_plane_url = os.environ.get("TG_CONTROL_PLANE_URL", "http://localhost:8000")
        parsed = urlparse(control_plane_url)

        if parsed.scheme != "https":
            self._add_check(
                "tls_certificate",
                "warning",
                "Not using HTTPS - TLS check skipped",
                {"scheme": parsed.scheme},
                (time.time() - start) * 1000
            )
            return

        try:
            host = parsed.hostname or "localhost"
            port = parsed.port or 443

            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()

                    # Check expiry
                    not_after = ssl.cert_time_to_seconds(cert['notAfter'])
                    days_until_expiry = (not_after - time.time()) / 86400

                    if days_until_expiry < 0:
                        self._add_check(
                            "tls_certificate",
                            "error",
                            "Certificate has expired",
                            {"expires": cert['notAfter'], "days_until_expiry": days_until_expiry},
                            (time.time() - start) * 1000
                        )
                    elif days_until_expiry < 30:
                        self._add_check(
                            "tls_certificate",
                            "warning",
                            f"Certificate expires in {int(days_until_expiry)} days",
                            {"expires": cert['notAfter'], "days_until_expiry": days_until_expiry},
                            (time.time() - start) * 1000
                        )
                    else:
                        self._add_check(
                            "tls_certificate",
                            "ok",
                            f"Certificate valid for {int(days_until_expiry)} days",
                            {"expires": cert['notAfter'], "days_until_expiry": days_until_expiry},
                            (time.time() - start) * 1000
                        )

        except ssl.SSLError as e:
            self._add_check(
                "tls_certificate",
                "error",
                f"SSL error: {str(e)}",
                {"error": str(e)},
                (time.time() - start) * 1000
            )
        except Exception as e:
            self._add_check(
                "tls_certificate",
                "error",
                f"TLS check error: {str(e)}",
                {"error": str(e)},
                (time.time() - start) * 1000
            )

    def check_file_permissions(self) -> None:
        """Check file system permissions for required directories."""
        start = time.time()

        data_dir = os.environ.get("TG_DATA_DIR", "./storage")
        config_dir = "./configs"
        keys_dir = "./keys"

        dirs_to_check = [
            (data_dir, "Data directory", True),  # (path, name, must_be_writable)
            (config_dir, "Config directory", False),
            (keys_dir, "Keys directory", False),
        ]

        issues = []
        for path, name, must_write in dirs_to_check:
            if not os.path.exists(path):
                if must_write:
                    # Try to create it
                    try:
                        os.makedirs(path, exist_ok=True)
                    except Exception as e:
                        issues.append(f"{name} ({path}): cannot create - {e}")
                        continue
                else:
                    continue  # Optional directory doesn't exist, that's ok

            if must_write and not os.access(path, os.W_OK):
                issues.append(f"{name} ({path}): not writable")

        if issues:
            self._add_check(
                "file_permissions",
                "error",
                f"{len(issues)} permission issue(s)",
                {"issues": issues},
                (time.time() - start) * 1000
            )
        else:
            self._add_check(
                "file_permissions",
                "ok",
                "File permissions OK",
                {"data_dir": data_dir},
                (time.time() - start) * 1000
            )

    def check_subsystem_availability(self) -> None:
        """Check availability of optional subsystems."""
        start = time.time()

        subsystems = []

        # Check ROS 2
        try:
            import rclpy
            subsystems.append(("ROS2", "ok", "Available"))
        except ImportError:
            subsystems.append(("ROS2", "warning", "Not installed"))

        # Check Flower (federated learning)
        try:
            import flwr
            subsystems.append(("Flower", "ok", "Available"))
        except ImportError:
            subsystems.append(("Flower", "warning", "Not installed"))

        # Check PyTorch
        try:
            import torch
            subsystems.append(("PyTorch", "ok", f"Version {torch.__version__}"))
        except ImportError:
            subsystems.append(("PyTorch", "warning", "Not installed"))

        # Check cryptography
        try:
            import cryptography
            subsystems.append(("Cryptography", "ok", f"Version {cryptography.__version__}"))
        except ImportError:
            subsystems.append(("Cryptography", "error", "Not installed - required"))

        for name, status, message in subsystems:
            self._add_check(
                f"subsystem_{name.lower()}",
                status,
                f"{name}: {message}",
                {},
                0
            )

    def check_system_resources(self) -> None:
        """Check system resource availability."""
        start = time.time()

        try:
            import shutil

            # Disk space
            data_dir = os.environ.get("TG_DATA_DIR", "./storage")
            if os.path.exists(data_dir):
                total, used, free = shutil.disk_usage(data_dir)
                free_gb = free / (1024 ** 3)
                if free_gb < 1:
                    self._add_check(
                        "disk_space",
                        "warning",
                        f"Low disk space: {free_gb:.1f} GB free",
                        {"free_gb": free_gb, "total_gb": total / (1024 ** 3)},
                        (time.time() - start) * 1000
                    )
                else:
                    self._add_check(
                        "disk_space",
                        "ok",
                        f"Disk space OK: {free_gb:.1f} GB free",
                        {"free_gb": free_gb, "total_gb": total / (1024 ** 3)},
                        (time.time() - start) * 1000
                    )
            else:
                self._add_check(
                    "disk_space",
                    "skipped",
                    "Data directory does not exist",
                    {},
                    0
                )

            # Memory (if psutil available)
            try:
                import psutil
                mem = psutil.virtual_memory()
                mem_available_gb = mem.available / (1024 ** 3)
                if mem_available_gb < 0.5:
                    self._add_check(
                        "memory",
                        "warning",
                        f"Low memory: {mem_available_gb:.1f} GB available",
                        {"available_gb": mem_available_gb, "total_gb": mem.total / (1024 ** 3)},
                        0
                    )
                else:
                    self._add_check(
                        "memory",
                        "ok",
                        f"Memory OK: {mem_available_gb:.1f} GB available",
                        {"available_gb": mem_available_gb, "total_gb": mem.total / (1024 ** 3)},
                        0
                    )
            except ImportError:
                self._add_check(
                    "memory",
                    "skipped",
                    "psutil not installed - memory check skipped",
                    {},
                    0
                )

        except Exception as e:
            self._add_check(
                "system_resources",
                "error",
                f"Resource check error: {str(e)}",
                {"error": str(e)},
                (time.time() - start) * 1000
            )

    def get_environment_info(self) -> Dict[str, Any]:
        """Collect environment information."""
        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
            "working_directory": os.getcwd(),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "control_plane_url": os.environ.get("TG_CONTROL_PLANE_URL", "http://localhost:8000"),
            "fleet_id": os.environ.get("TG_FLEET_ID", ""),
            "agent_name": os.environ.get("TG_AGENT_NAME", socket.gethostname()),
        }

    def run_full_diagnosis(self) -> DiagnosticReport:
        """Run all diagnostic checks and generate report."""
        self.checks = []

        if self.verbose:
            print("\n=== TensorGuard Agent Diagnostics ===\n")
            print("Running checks...\n")

        # Run all checks
        self.check_environment()
        self.check_control_plane_connectivity()
        self.check_tls_certificates()
        self.check_file_permissions()
        self.check_subsystem_availability()
        self.check_system_resources()

        # Calculate summary
        summary = {"ok": 0, "warning": 0, "error": 0, "skipped": 0}
        for check in self.checks:
            summary[check.status] = summary.get(check.status, 0) + 1

        # Determine overall status
        if summary["error"] > 0:
            overall = "unhealthy"
        elif summary["warning"] > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        report = DiagnosticReport(
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent_version=self.VERSION,
            overall_status=overall,
            checks=self.checks,
            environment=self.get_environment_info(),
            summary=summary,
        )

        if self.verbose:
            print(f"\n=== Summary ===")
            print(f"Status: {overall.upper()}")
            print(f"  OK: {summary['ok']}, Warnings: {summary['warning']}, Errors: {summary['error']}, Skipped: {summary['skipped']}")

        return report


def main():
    """CLI entry point for agent diagnostics."""
    parser = argparse.ArgumentParser(
        description="TensorGuard Agent Diagnostics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tensorguard.agent.diagnose              # Run diagnostics
  python -m tensorguard.agent.diagnose --verbose    # Verbose output
  python -m tensorguard.agent.diagnose --json       # JSON output
        """
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output with progress"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()

    diag = AgentDiagnostics(verbose=args.verbose and not args.json)
    report = diag.run_full_diagnosis()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif not args.verbose:
        # Default compact output
        print(f"\nAgent Diagnostics Report")
        print(f"========================")
        print(f"Status: {report.overall_status.upper()}")
        print(f"Checks: {report.summary['ok']} OK, {report.summary['warning']} warnings, {report.summary['error']} errors")
        print()

        if report.overall_status != "healthy":
            print("Issues found:")
            for check in report.checks:
                if check.status in ("error", "warning"):
                    print(f"  - [{check.status.upper()}] {check.name}: {check.message}")

    # Exit with appropriate code
    if report.overall_status == "unhealthy":
        sys.exit(1)
    elif report.overall_status == "degraded":
        sys.exit(0)  # Warnings are not fatal
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
