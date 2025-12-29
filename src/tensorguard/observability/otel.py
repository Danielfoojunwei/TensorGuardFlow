"""
OpenTelemetry Setup for MOAI
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

def setup_otel(service_name: str = "moai-inference"):
    """
    Initialize OpenTelemetry. 
    For production, this would configure OTLP exporters.
    """
    provider = TracerProvider()
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    
    return trace.get_tracer(service_name)
