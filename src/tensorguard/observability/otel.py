"""
OpenTelemetry Setup for TensorGuard

Provides production-ready observability with:
- Distributed tracing via OpenTelemetry
- Metrics export to Prometheus
- Structured logging correlation
- Configurable exporters (OTLP, Console, Jaeger)

Configuration:
    TG_ENABLE_OTEL=true          Enable OpenTelemetry
    TG_OTEL_ENDPOINT=<url>       OTLP collector endpoint (default: localhost:4317)
    TG_OTEL_EXPORTER=otlp        Exporter type: otlp, console, jaeger
    TG_ENABLE_PROMETHEUS=true    Enable Prometheus metrics
    TG_PROMETHEUS_PORT=9090      Prometheus metrics port

Usage:
    from tensorguard.observability.otel import setup_observability, get_tracer

    # Initialize at application startup
    setup_observability("tensorguard-platform")

    # Get tracer for instrumentation
    tracer = get_tracer()
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("user_id", "123")
        # ... do work
"""

import os
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Check for OpenTelemetry availability
OTEL_AVAILABLE = False
PROMETHEUS_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        ConsoleSpanExporter,
        SimpleSpanProcessor,
        BatchSpanProcessor,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    OTEL_AVAILABLE = True
except ImportError:
    logger.warning("OpenTelemetry SDK not installed. Tracing disabled. Install: pip install opentelemetry-sdk")

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.info("prometheus_client not installed. Metrics disabled. Install: pip install prometheus-client")


# Global tracer instance
_tracer: Optional["trace.Tracer"] = None
_initialized = False


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

if PROMETHEUS_AVAILABLE:
    # Request metrics
    REQUEST_COUNT = Counter(
        'tensorguard_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
    REQUEST_LATENCY = Histogram(
        'tensorguard_request_latency_seconds',
        'Request latency in seconds',
        ['method', 'endpoint'],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )

    # Training metrics
    TRAINING_ROUNDS = Counter(
        'tensorguard_training_rounds_total',
        'Total federated learning rounds',
        ['status']
    )
    DP_EPSILON_CONSUMED = Gauge(
        'tensorguard_dp_epsilon_consumed',
        'Cumulative differential privacy epsilon consumed',
        ['client_id']
    )

    # Crypto metrics
    ENCRYPTION_OPS = Counter(
        'tensorguard_encryption_operations_total',
        'Total encryption operations',
        ['operation', 'algorithm']
    )
    KEY_ROTATIONS = Counter(
        'tensorguard_key_rotations_total',
        'Total key rotation events',
        ['key_type']
    )

    # Health metrics
    ACTIVE_CONNECTIONS = Gauge(
        'tensorguard_active_connections',
        'Number of active client connections'
    )
    AGGREGATION_QUEUE_SIZE = Gauge(
        'tensorguard_aggregation_queue_size',
        'Number of pending client contributions'
    )

    # Security metrics
    AUTH_FAILURES = Counter(
        'tensorguard_auth_failures_total',
        'Total authentication failures',
        ['reason']  # invalid_token, expired, user_not_found, etc.
    )
    AUTH_SUCCESS = Counter(
        'tensorguard_auth_success_total',
        'Total successful authentications',
        ['method']  # jwt, api_key, fleet
    )

    # Policy metrics
    POLICY_DENIALS = Counter(
        'tensorguard_policy_denials_total',
        'Total policy-based access denials',
        ['policy', 'resource']
    )
    POLICY_EVALUATIONS = Counter(
        'tensorguard_policy_evaluations_total',
        'Total policy evaluations',
        ['policy', 'result']  # allow, deny
    )

    # Job metrics
    JOB_FAILURES = Counter(
        'tensorguard_job_failures_total',
        'Total job failures',
        ['job_type', 'reason']
    )
    JOB_COMPLETIONS = Counter(
        'tensorguard_job_completions_total',
        'Total job completions',
        ['job_type', 'status']  # success, failed, cancelled
    )
    JOB_DURATION = Histogram(
        'tensorguard_job_duration_seconds',
        'Job execution duration',
        ['job_type'],
        buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
    )

    # Vault metrics
    VAULT_OPS = Counter(
        'tensorguard_vault_operations_total',
        'Total vault operations',
        ['operation']  # save, load, delete, export, import
    )
    VAULT_ERRORS = Counter(
        'tensorguard_vault_errors_total',
        'Total vault operation errors',
        ['operation', 'error_type']
    )
    VAULT_KEYS_TOTAL = Gauge(
        'tensorguard_vault_keys_total',
        'Total number of keys in vault',
        ['scope']  # identity, inference, aggregation, system
    )

    # SLO metrics
    SLO_REQUEST_LATENCY = Histogram(
        'tensorguard_slo_request_latency_seconds',
        'Request latency for SLO tracking (p50, p95, p99)',
        ['endpoint_group'],  # auth, api, health
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
    )
    SLO_AVAILABILITY = Gauge(
        'tensorguard_slo_availability_ratio',
        'Current availability ratio (successful requests / total)',
        ['service']
    )


def setup_observability(
    service_name: str = "tensorguard",
    enable_tracing: bool = None,
    enable_metrics: bool = None,
) -> None:
    """
    Initialize observability stack (tracing + metrics).

    Args:
        service_name: Service name for trace attribution
        enable_tracing: Override TG_ENABLE_OTEL env var
        enable_metrics: Override TG_ENABLE_PROMETHEUS env var
    """
    global _tracer, _initialized

    if _initialized:
        logger.debug("Observability already initialized")
        return

    # Read from environment if not explicitly set
    if enable_tracing is None:
        enable_tracing = os.getenv("TG_ENABLE_OTEL", "false").lower() == "true"
    if enable_metrics is None:
        enable_metrics = os.getenv("TG_ENABLE_PROMETHEUS", "false").lower() == "true"

    # Setup tracing
    if enable_tracing and OTEL_AVAILABLE:
        _tracer = _setup_tracing(service_name)
        logger.info(f"OpenTelemetry tracing enabled for service: {service_name}")
    elif enable_tracing:
        logger.warning("Tracing requested but OpenTelemetry SDK not available")

    # Setup metrics
    if enable_metrics and PROMETHEUS_AVAILABLE:
        port = int(os.getenv("TG_PROMETHEUS_PORT", "9090"))
        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")
    elif enable_metrics:
        logger.warning("Metrics requested but prometheus_client not available")

    _initialized = True


def _setup_tracing(service_name: str) -> "trace.Tracer":
    """Configure OpenTelemetry tracing."""
    # Create resource with service info
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: os.getenv("TG_VERSION", "2.3.0"),
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv("TG_ENVIRONMENT", "development"),
    })

    provider = TracerProvider(resource=resource)

    # Configure exporter based on environment
    exporter_type = os.getenv("TG_OTEL_EXPORTER", "console").lower()
    endpoint = os.getenv("TG_OTEL_ENDPOINT", "http://localhost:4317")

    if exporter_type == "otlp" and OTLP_AVAILABLE:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        processor = BatchSpanProcessor(exporter)
        logger.info(f"OTLP exporter configured: {endpoint}")
    else:
        exporter = ConsoleSpanExporter()
        processor = SimpleSpanProcessor(exporter)
        if exporter_type == "otlp":
            logger.warning("OTLP requested but exporter not available, using console")

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    return trace.get_tracer(service_name)


def get_tracer(name: str = None) -> "trace.Tracer":
    """
    Get a tracer instance.

    Returns a no-op tracer if observability is not initialized or available.
    """
    global _tracer

    if _tracer is not None:
        return _tracer

    if OTEL_AVAILABLE:
        # Return default tracer if not explicitly configured
        return trace.get_tracer(name or "tensorguard")

    # Return a no-op tracer stub
    class NoOpSpan:
        def set_attribute(self, key, value): pass
        def add_event(self, name, attributes=None): pass
        def record_exception(self, exception): pass
        def set_status(self, status): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass

    class NoOpTracer:
        def start_as_current_span(self, name, **kwargs):
            return NoOpSpan()
        def start_span(self, name, **kwargs):
            return NoOpSpan()

    return NoOpTracer()


@contextmanager
def trace_operation(name: str, attributes: dict = None):
    """
    Context manager for tracing an operation.

    Usage:
        with trace_operation("process_update", {"client_id": "123"}):
            # ... do work
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            raise


# Legacy compatibility
def setup_otel(service_name: str = "moai-inference"):
    """
    Legacy function for backward compatibility.
    Use setup_observability() for new code.
    """
    setup_observability(service_name, enable_tracing=True)
    return get_tracer(service_name)


# =============================================================================
# METRICS MIDDLEWARE
# =============================================================================

class MetricsMiddleware:
    """
    ASGI Middleware for automatic request metrics collection.

    Tracks:
    - Request count by method, endpoint, status
    - Request latency histogram
    - SLO latency for endpoint groups

    Usage:
        from tensorguard.observability.otel import MetricsMiddleware
        app.add_middleware(MetricsMiddleware)
    """

    ENDPOINT_GROUPS = {
        '/auth': 'auth',
        '/api/v1/auth': 'auth',
        '/health': 'health',
        '/healthz': 'health',
        '/ready': 'health',
        '/readyz': 'health',
        '/live': 'health',
        '/metrics': 'health',
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time
        start_time = time.time()
        status_code = 500  # Default in case of error

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if PROMETHEUS_AVAILABLE:
                duration = time.time() - start_time
                path = scope.get("path", "/unknown")
                method = scope.get("method", "UNKNOWN")

                # Normalize path for metrics (remove IDs)
                normalized_path = self._normalize_path(path)

                # Record request metrics
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=normalized_path,
                    status=str(status_code)
                ).inc()

                REQUEST_LATENCY.labels(
                    method=method,
                    endpoint=normalized_path
                ).observe(duration)

                # Record SLO latency for endpoint group
                endpoint_group = self._get_endpoint_group(path)
                if endpoint_group:
                    SLO_REQUEST_LATENCY.labels(
                        endpoint_group=endpoint_group
                    ).observe(duration)

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders."""
        import re
        # Replace UUIDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        return path

    def _get_endpoint_group(self, path: str) -> str:
        """Get the endpoint group for SLO tracking."""
        for prefix, group in self.ENDPOINT_GROUPS.items():
            if path.startswith(prefix):
                return group
        if path.startswith('/api'):
            return 'api'
        return 'other'


# =============================================================================
# HELPER FUNCTIONS FOR METRICS
# =============================================================================

def record_auth_success(method: str = "jwt"):
    """Record a successful authentication."""
    if PROMETHEUS_AVAILABLE:
        AUTH_SUCCESS.labels(method=method).inc()


def record_auth_failure(reason: str):
    """Record an authentication failure."""
    if PROMETHEUS_AVAILABLE:
        AUTH_FAILURES.labels(reason=reason).inc()


def record_policy_evaluation(policy: str, result: str, resource: str = None):
    """Record a policy evaluation."""
    if PROMETHEUS_AVAILABLE:
        POLICY_EVALUATIONS.labels(policy=policy, result=result).inc()
        if result == "deny" and resource:
            POLICY_DENIALS.labels(policy=policy, resource=resource).inc()


def record_vault_operation(operation: str):
    """Record a vault operation."""
    if PROMETHEUS_AVAILABLE:
        VAULT_OPS.labels(operation=operation).inc()


def record_vault_error(operation: str, error_type: str):
    """Record a vault operation error."""
    if PROMETHEUS_AVAILABLE:
        VAULT_ERRORS.labels(operation=operation, error_type=error_type).inc()


def record_job_completion(job_type: str, status: str, duration_seconds: float = None):
    """Record a job completion."""
    if PROMETHEUS_AVAILABLE:
        JOB_COMPLETIONS.labels(job_type=job_type, status=status).inc()
        if duration_seconds is not None:
            JOB_DURATION.labels(job_type=job_type).observe(duration_seconds)
        if status == "failed":
            JOB_FAILURES.labels(job_type=job_type, reason="execution_error").inc()


def get_current_trace_id() -> str:
    """Get the current trace ID for log correlation."""
    if not OTEL_AVAILABLE:
        return ""

    try:
        current_span = trace.get_current_span()
        if current_span:
            ctx = current_span.get_span_context()
            if ctx.is_valid:
                return format(ctx.trace_id, '032x')
    except Exception:
        pass
    return ""


def get_current_span_id() -> str:
    """Get the current span ID for log correlation."""
    if not OTEL_AVAILABLE:
        return ""

    try:
        current_span = trace.get_current_span()
        if current_span:
            ctx = current_span.get_span_context()
            if ctx.is_valid:
                return format(ctx.span_id, '016x')
    except Exception:
        pass
    return ""
