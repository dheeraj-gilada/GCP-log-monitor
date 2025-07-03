from contextlib import contextmanager
from typing import Optional, Dict, Any
import logging

try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, Tracer
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:
    trace = None
    Span = None
    Tracer = None
    TraceContextTextMapPropagator = None

import uuid

@contextmanager
def start_trace(name: str):
    """
    Context manager for starting an OpenTelemetry trace span.
    Falls back to no-op if OpenTelemetry is not available.
    """
    if trace and trace.get_tracer:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(name) as span:
            yield span
    else:
        yield None


def set_correlation_context(span: Optional[Any], log: Any):
    """
    Attach trace/span info to a log entry if a span is active.
    """
    if not span:
        return
    try:
        if hasattr(log, 'correlation_context') and log.correlation_context is not None:
            log.correlation_context['trace_id'] = str(span.get_span_context().trace_id)
            log.correlation_context['span_id'] = str(span.get_span_context().span_id)
        elif hasattr(log, 'correlation_context'):
            log.correlation_context = {
                'trace_id': str(span.get_span_context().trace_id),
                'span_id': str(span.get_span_context().span_id)
            }
    except Exception as e:
        logging.warning(f"Failed to set correlation context: {e}")


def extract_correlation_context(log: Any) -> Dict[str, Any]:
    """
    Extract correlation context (trace_id, span_id, etc.) from a log entry.
    """
    context = {}
    try:
        if hasattr(log, 'correlation_context') and log.correlation_context:
            context = dict(log.correlation_context)
        elif hasattr(log, 'trace') and log.trace:
            context['trace_id'] = log.trace
        if hasattr(log, 'span_id') and log.span_id:
            context['span_id'] = log.span_id
    except Exception as e:
        logging.warning(f"Failed to extract correlation context: {e}")
    return context


def generate_trace_id() -> str:
    """
    Generate a random trace ID (hex string).
    """
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """
    Generate a random span ID (hex string).
    """
    return uuid.uuid4().hex[:16] 