"""
Platform Worker Unit Tests

Tests for the background worker including:
- Worker metrics tracking
- Feature flag integration
- Graceful shutdown
- Health checks

Run with: pytest tests/unit/test_worker.py -v
"""

import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestWorkerMetrics:
    """Test WorkerMetrics dataclass."""

    def test_metrics_initialization(self):
        """WorkerMetrics should initialize with defaults."""
        from tensorguard.platform.worker import WorkerMetrics

        metrics = WorkerMetrics()
        assert metrics.loops_completed == 0
        assert metrics.identity_jobs_processed == 0
        assert metrics.errors_count == 0
        assert metrics.last_error is None
        assert isinstance(metrics.started_at, datetime)

    def test_metrics_record_error(self):
        """record_error should track error information."""
        from tensorguard.platform.worker import WorkerMetrics

        metrics = WorkerMetrics()
        assert metrics.errors_count == 0

        metrics.record_error("Test error")
        assert metrics.errors_count == 1
        assert metrics.last_error == "Test error"
        assert metrics.last_error_at is not None

        metrics.record_error("Another error")
        assert metrics.errors_count == 2
        assert metrics.last_error == "Another error"

    def test_metrics_to_dict(self):
        """to_dict should return complete metrics dictionary."""
        from tensorguard.platform.worker import WorkerMetrics

        metrics = WorkerMetrics()
        metrics.loops_completed = 5
        metrics.identity_jobs_processed = 3

        result = metrics.to_dict()
        assert "started_at" in result
        assert "uptime_seconds" in result
        assert "loops_completed" in result
        assert result["loops_completed"] == 5
        assert result["identity_jobs_processed"] == 3
        assert "healthy" in result

    def test_metrics_healthy_with_no_errors(self):
        """Metrics should show healthy when no errors."""
        from tensorguard.platform.worker import WorkerMetrics

        metrics = WorkerMetrics()
        result = metrics.to_dict()
        assert result["healthy"] is True

    def test_metrics_healthy_after_error_cooldown(self):
        """Metrics should show healthy if error was > 5 minutes ago."""
        from tensorguard.platform.worker import WorkerMetrics

        metrics = WorkerMetrics()
        metrics.record_error("Old error")
        # Simulate old error
        metrics.last_error_at = datetime.utcnow() - timedelta(minutes=10)

        result = metrics.to_dict()
        assert result["healthy"] is True


class TestGracefulExit:
    """Test GracefulExit handler."""

    def test_graceful_exit_initial_state(self):
        """GracefulExit should start with exit_now=False."""
        from tensorguard.platform.worker import GracefulExit

        # Need to mock signal to avoid interfering with test runner
        with patch('signal.signal'):
            exiter = GracefulExit()
            assert exiter.should_exit() is False

    def test_graceful_exit_handle_signal(self):
        """handle_exit should set exit flag."""
        from tensorguard.platform.worker import GracefulExit

        with patch('signal.signal'):
            exiter = GracefulExit()
            exiter.handle_exit(15, None)  # SIGTERM
            assert exiter.should_exit() is True


class TestPlatformWorker:
    """Test PlatformWorker class."""

    def test_worker_initialization(self):
        """PlatformWorker should initialize with correct defaults."""
        from tensorguard.platform.worker import PlatformWorker

        with patch('signal.signal'):
            worker = PlatformWorker()
            assert worker.interval == 10
            assert worker.metrics is not None
            assert worker.metrics.loops_completed == 0

    def test_worker_custom_interval(self):
        """Worker should respect TG_WORKER_INTERVAL environment variable."""
        from tensorguard.platform.worker import PlatformWorker

        with patch.dict(os.environ, {"TG_WORKER_INTERVAL": "30"}):
            with patch('signal.signal'):
                worker = PlatformWorker()
                assert worker.interval == 30

    def test_worker_get_health(self):
        """get_health should return health status dict."""
        from tensorguard.platform.worker import PlatformWorker

        with patch('signal.signal'):
            worker = PlatformWorker()
            health = worker.get_health()

            assert "status" in health
            assert "metrics" in health
            assert "feature_flags" in health
            assert health["status"] in ["healthy", "degraded"]

    def test_worker_identity_renewals_disabled(self):
        """process_identity_renewals should skip when disabled."""
        from tensorguard.platform.worker import PlatformWorker

        with patch.dict(os.environ, {"TG_WORKER_IDENTITY_RENEWAL": "false"}):
            with patch('signal.signal'):
                # Reload to pick up env change
                from tensorguard.utils import feature_flags
                from importlib import reload
                reload(feature_flags)

                worker = PlatformWorker()
                result = worker.process_identity_renewals()
                assert result == 0

        # Restore
        with patch.dict(os.environ, {"TG_WORKER_IDENTITY_RENEWAL": "true"}):
            from tensorguard.utils import feature_flags
            from importlib import reload
            reload(feature_flags)

    def test_worker_telemetry_aggregation_disabled(self):
        """process_telemetry_aggregation should skip when disabled."""
        from tensorguard.platform.worker import PlatformWorker

        with patch.dict(os.environ, {"TG_WORKER_TELEMETRY_AGGREGATION": "false"}):
            with patch('signal.signal'):
                from tensorguard.utils import feature_flags
                from importlib import reload
                reload(feature_flags)

                worker = PlatformWorker()
                result = worker.process_telemetry_aggregation()
                assert result == 0

        # Restore
        with patch.dict(os.environ, {"TG_WORKER_TELEMETRY_AGGREGATION": "true"}):
            from tensorguard.utils import feature_flags
            from importlib import reload
            reload(feature_flags)

    def test_worker_job_cleanup_disabled(self):
        """cleanup_stale_jobs should skip when disabled."""
        from tensorguard.platform.worker import PlatformWorker

        with patch.dict(os.environ, {"TG_WORKER_JOB_CLEANUP": "false"}):
            with patch('signal.signal'):
                from tensorguard.utils import feature_flags
                from importlib import reload
                reload(feature_flags)

                worker = PlatformWorker()
                result = worker.cleanup_stale_jobs()
                assert result == 0

        # Restore
        with patch.dict(os.environ, {"TG_WORKER_JOB_CLEANUP": "true"}):
            from tensorguard.utils import feature_flags
            from importlib import reload
            reload(feature_flags)

    def test_worker_run_loop_iteration(self):
        """run_loop_iteration should update metrics."""
        from tensorguard.platform.worker import PlatformWorker

        with patch('signal.signal'):
            worker = PlatformWorker()

            # Mock the database session to avoid actual DB calls
            with patch('tensorguard.platform.worker.SessionLocal'):
                worker.run_loop_iteration()

            assert worker.metrics.loops_completed == 1
            assert worker.metrics.last_loop_at is not None


class TestWorkerIntegration:
    """Integration tests for worker with database."""

    def test_worker_handles_db_errors_gracefully(self):
        """Worker should handle database errors without crashing."""
        from tensorguard.platform.worker import PlatformWorker

        with patch('signal.signal'):
            worker = PlatformWorker()

            # Simulate DB error
            with patch('tensorguard.platform.worker.SessionLocal') as mock_session:
                mock_session.side_effect = Exception("DB connection failed")

                # Should not raise
                result = worker.process_identity_renewals()

            # Should record error
            assert worker.metrics.errors_count > 0
            assert "identity_renewal" in worker.metrics.last_error

    def test_worker_handles_cleanup_errors_gracefully(self):
        """Worker should handle cleanup errors without crashing."""
        from tensorguard.platform.worker import PlatformWorker

        with patch('signal.signal'):
            worker = PlatformWorker()

            # Simulate DB error
            with patch('tensorguard.platform.worker.SessionLocal') as mock_session:
                mock_session.side_effect = Exception("DB connection failed")

                # Should not raise
                result = worker.cleanup_stale_jobs()

            # Should record error
            assert worker.metrics.errors_count > 0


class TestRunWorkerLoop:
    """Test the run_worker_loop entry point."""

    def test_run_worker_loop_creates_worker(self):
        """run_worker_loop should create and run PlatformWorker."""
        from tensorguard.platform.worker import run_worker_loop, PlatformWorker

        with patch('signal.signal'):
            with patch.object(PlatformWorker, 'run') as mock_run:
                # Make the worker exit immediately
                mock_run.return_value = None
                run_worker_loop()
                mock_run.assert_called_once()
