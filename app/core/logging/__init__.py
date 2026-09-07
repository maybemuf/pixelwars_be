import atexit
import logging
import logging.config
import pathlib

import yaml
from opentelemetry import trace

from .json_formatter import AppJSONFormatter

CONFIG_FILE = pathlib.Path("logging_config.yaml")


class TraceContextFilter(logging.Filter):
    """Stamp the active trace onto every record.

    The formats need otelTraceID unconditionally, but OTel's own
    LoggingInstrumentor stamps it only on records created after
    setup_telemetry() has run — and never at all when OTEL_ENABLED=false.
    Everything logged before that raised KeyError. get_current_span() is safe
    either way: with no provider installed it yields an invalid context, and
    we fall back to the same "0" placeholders the instrumentor uses.

    Sits on queue_handler so it runs in the thread that logged, not in the
    listener thread, where the span context would already be gone.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            record.otelTraceID = format(ctx.trace_id, "032x")
            record.otelSpanID = format(ctx.span_id, "016x")
            record.otelTraceSampled = ctx.trace_flags.sampled
        else:
            record.otelTraceID = "0"
            record.otelSpanID = "0"
            record.otelTraceSampled = False
        return True


def setup_logging(json_logs: bool = False):
    config = yaml.safe_load(CONFIG_FILE.read_text())
    if json_logs:
        config["handlers"]["stdout"]["formatter"] = "json"

    logging.config.dictConfig(config)

    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)

__all__ = ["setup_logging", "AppJSONFormatter", "TraceContextFilter"]
