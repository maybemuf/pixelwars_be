import logging
import socket

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_INSTANCE_ID, SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core import settings

LOGS_ENDPOINT = f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/logs"
TRACES_ENDPOINT = f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces"
METRIC_ENDPOINT = f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/metrics"

logger = logging.getLogger(__name__)

tracer = trace.get_tracer("pixelwars")
meter = metrics.get_meter("pixelwars")


def setup_telemetry(app: FastAPI):
    if not settings.OTEL_ENABLED:
        logger.info("telemetry disabled (OTEL_ENABLED=false): no traces or metrics will be exported")
        return

    resource = Resource.create(
        attributes={
            SERVICE_NAME: "pixelwars-api",
            SERVICE_VERSION: settings.API_VERSION,
            SERVICE_INSTANCE_ID: socket.gethostname(),
            "deployment.enviroment": settings.ENVIROMENT,
        }
    )
    is_dev = settings.ENVIROMENT == "dev"

    # Setting up LOGS
    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=LOGS_ENDPOINT)))
    set_logger_provider(lp)

    # Setting up TRACES
    tracer_provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=TRACES_ENDPOINT))
    tracer_provider.add_span_processor(processor)
    if is_dev:
        console_processor = BatchSpanProcessor(ConsoleSpanExporter())
        tracer_provider.add_span_processor(console_processor)

    trace.set_tracer_provider(tracer_provider)

    # Setting up METRICS
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=METRIC_ENDPOINT))
    console_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[reader, console_reader] if is_dev else [reader],
    )
    metrics.set_meter_provider(meter_provider)


    logger.info("telemetry enabled: exporting to %s", settings.OTEL_EXPORTER_OTLP_ENDPOINT)

    FastAPIInstrumentor.instrument_app(app)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    LoggingInstrumentor().instrument(inject_trace_context=True)

