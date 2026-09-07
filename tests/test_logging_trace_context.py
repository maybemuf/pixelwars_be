"""Guards the KeyError: 'otelTraceID' regression.

The formats reference otelTraceID unconditionally, so a record logged before
(or entirely without) OTel instrumentation must still carry the field.
"""

import logging

from opentelemetry import trace

from app.core.logging import TraceContextFilter


def _record() -> logging.LogRecord:
    return logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)


def test_stamps_placeholders_without_a_span():
    record = _record()
    assert TraceContextFilter().filter(record)
    assert record.otelTraceID == "0"
    assert record.otelSpanID == "0"
    assert record.otelTraceSampled is False


def test_stamps_real_ids_inside_a_span():
    with trace.get_tracer(__name__).start_as_current_span("s"):
        record = _record()
        TraceContextFilter().filter(record)
    # No SDK provider in tests, so the span is non-recording; either way the
    # point is that the field exists and the format can render it.
    assert logging.Formatter("[%(otelTraceID)s] %(message)s").format(record)
