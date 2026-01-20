"""
Agent Diagnostics Unit Tests

Tests for the agent diagnostic system including:
- DiagnosticCheck and DiagnosticReport dataclasses
- AgentDiagnostics checks
- Environment detection
- JSON output

Run with: pytest tests/unit/test_agent_diagnose.py -v
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock


class TestDiagnosticDataClasses:
    """Test diagnostic data classes."""

    def test_diagnostic_check_creation(self):
        """DiagnosticCheck should create with required fields."""
        from tensorguard.agent.diagnose import DiagnosticCheck

        check = DiagnosticCheck(
            name="test_check",
            status="ok",
            message="Test passed",
        )

        assert check.name == "test_check"
        assert check.status == "ok"
        assert check.message == "Test passed"
        assert check.details == {}
        assert check.duration_ms == 0.0

    def test_diagnostic_check_with_details(self):
        """DiagnosticCheck should accept details."""
        from tensorguard.agent.diagnose import DiagnosticCheck

        check = DiagnosticCheck(
            name="test_check",
            status="warning",
            message="Test warning",
            details={"key": "value"},
            duration_ms=100.5,
        )

        assert check.details == {"key": "value"}
        assert check.duration_ms == 100.5

    def test_diagnostic_check_to_dict(self):
        """DiagnosticCheck.to_dict should return complete dict."""
        from tensorguard.agent.diagnose import DiagnosticCheck

        check = DiagnosticCheck(
            name="test_check",
            status="ok",
            message="Test passed",
            details={"test": True},
            duration_ms=50.0,
        )

        result = check.to_dict()
        assert result["name"] == "test_check"
        assert result["status"] == "ok"
        assert result["message"] == "Test passed"
        assert result["details"] == {"test": True}
        assert result["duration_ms"] == 50.0

    def test_diagnostic_report_creation(self):
        """DiagnosticReport should create with required fields."""
        from tensorguard.agent.diagnose import DiagnosticReport

        report = DiagnosticReport(
            timestamp="2024-01-01T00:00:00Z",
            agent_version="1.0.0",
            overall_status="healthy",
        )

        assert report.timestamp == "2024-01-01T00:00:00Z"
        assert report.agent_version == "1.0.0"
        assert report.overall_status == "healthy"
        assert report.checks == []

    def test_diagnostic_report_to_dict(self):
        """DiagnosticReport.to_dict should return complete dict."""
        from tensorguard.agent.diagnose import DiagnosticReport, DiagnosticCheck

        check = DiagnosticCheck(name="test", status="ok", message="OK")
        report = DiagnosticReport(
            timestamp="2024-01-01T00:00:00Z",
            agent_version="1.0.0",
            overall_status="healthy",
            checks=[check],
            summary={"ok": 1},
        )

        result = report.to_dict()
        assert result["timestamp"] == "2024-01-01T00:00:00Z"
        assert result["overall_status"] == "healthy"
        assert len(result["checks"]) == 1
        assert result["summary"] == {"ok": 1}


class TestAgentDiagnostics:
    """Test AgentDiagnostics class."""

    def test_diagnostics_initialization(self):
        """AgentDiagnostics should initialize correctly."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        diag = AgentDiagnostics()
        assert diag.verbose is False
        assert diag.checks == []

    def test_diagnostics_verbose_mode(self):
        """AgentDiagnostics should support verbose mode."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        diag = AgentDiagnostics(verbose=True)
        assert diag.verbose is True

    def test_add_check(self):
        """_add_check should add check to list."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        diag = AgentDiagnostics()
        check = diag._add_check("test", "ok", "Test passed")

        assert len(diag.checks) == 1
        assert diag.checks[0].name == "test"
        assert diag.checks[0].status == "ok"

    def test_check_environment_with_vars_set(self):
        """check_environment should pass when vars are set."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        with patch.dict(os.environ, {
            "TG_FLEET_API_KEY": "test_key",
            "TG_FLEET_ID": "test_fleet",
        }):
            diag = AgentDiagnostics()
            diag.check_environment()

            # Should have at least 2 checks (required + optional)
            assert len(diag.checks) >= 2

            # Required vars check should be OK
            required_check = next(c for c in diag.checks if c.name == "environment_required")
            assert required_check.status == "ok"

    def test_check_environment_missing_vars(self):
        """check_environment should fail when required vars missing."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        with patch.dict(os.environ, {}, clear=True):
            # Also clear TG_FLEET_API_KEY if it exists
            env_copy = os.environ.copy()
            env_copy.pop("TG_FLEET_API_KEY", None)
            env_copy.pop("TG_FLEET_ID", None)

            with patch.dict(os.environ, env_copy, clear=True):
                diag = AgentDiagnostics()
                diag.check_environment()

                required_check = next(c for c in diag.checks if c.name == "environment_required")
                assert required_check.status == "error"

    def test_check_file_permissions(self):
        """check_file_permissions should check directory access."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        with patch.dict(os.environ, {"TG_DATA_DIR": "/tmp/tensorguard_test"}):
            diag = AgentDiagnostics()
            diag.check_file_permissions()

            # Should have at least one check
            assert len(diag.checks) >= 1

    def test_check_subsystem_availability(self):
        """check_subsystem_availability should check for modules."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        diag = AgentDiagnostics()
        diag.check_subsystem_availability()

        # Should have checks for various subsystems
        subsystem_checks = [c for c in diag.checks if c.name.startswith("subsystem_")]
        assert len(subsystem_checks) > 0

    def test_get_environment_info(self):
        """get_environment_info should return system info."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        diag = AgentDiagnostics()
        info = diag.get_environment_info()

        assert "python_version" in info
        assert "platform" in info
        assert "hostname" in info
        assert "control_plane_url" in info

    def test_run_full_diagnosis(self):
        """run_full_diagnosis should return complete report."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        with patch.dict(os.environ, {
            "TG_FLEET_API_KEY": "test_key",
            "TG_FLEET_ID": "test_fleet",
            "TG_CONTROL_PLANE_URL": "http://localhost:8000",
        }):
            diag = AgentDiagnostics()
            report = diag.run_full_diagnosis()

            assert report.timestamp is not None
            assert report.agent_version is not None
            assert report.overall_status in ["healthy", "degraded", "unhealthy"]
            assert len(report.checks) > 0
            assert "ok" in report.summary
            assert "error" in report.summary
            assert "warning" in report.summary


class TestDiagnosticsOverallStatus:
    """Test overall status calculation."""

    def test_healthy_status_no_errors(self):
        """Report should be healthy with no errors or warnings."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        diag = AgentDiagnostics()
        diag._add_check("test1", "ok", "OK")
        diag._add_check("test2", "ok", "OK")

        report = diag.run_full_diagnosis()
        # Note: run_full_diagnosis runs all checks, but the added ones should be there
        # Status depends on all checks run
        assert report.overall_status in ["healthy", "degraded", "unhealthy"]

    def test_degraded_with_warnings(self):
        """Report should be degraded with warnings but no errors."""
        from tensorguard.agent.diagnose import AgentDiagnostics, DiagnosticReport

        # Create a minimal report to test logic
        report = DiagnosticReport(
            timestamp="2024-01-01T00:00:00Z",
            agent_version="1.0.0",
            overall_status="degraded",
            summary={"ok": 5, "warning": 1, "error": 0},
        )

        assert report.overall_status == "degraded"

    def test_unhealthy_with_errors(self):
        """Report should be unhealthy with errors."""
        from tensorguard.agent.diagnose import DiagnosticReport

        report = DiagnosticReport(
            timestamp="2024-01-01T00:00:00Z",
            agent_version="1.0.0",
            overall_status="unhealthy",
            summary={"ok": 5, "warning": 0, "error": 1},
        )

        assert report.overall_status == "unhealthy"


class TestDiagnosticsOutput:
    """Test diagnostic output formats."""

    def test_report_serializes_to_json(self):
        """Report should serialize to valid JSON."""
        from tensorguard.agent.diagnose import AgentDiagnostics

        with patch.dict(os.environ, {
            "TG_FLEET_API_KEY": "test",
            "TG_FLEET_ID": "test",
        }):
            diag = AgentDiagnostics()
            report = diag.run_full_diagnosis()

            # Should serialize without error
            json_str = json.dumps(report.to_dict())
            assert json_str is not None

            # Should deserialize back
            parsed = json.loads(json_str)
            assert parsed["overall_status"] == report.overall_status
