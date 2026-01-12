"""
Distributed tracing with OpenTelemetry.

Traces requests across API, database, Redis, and Celery.
"""
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = structlog.get_logger()


def setup_tracing(app: "FastAPI") -> None:
    """
    Configure OpenTelemetry tracing for the application.

    Requires OTLP_ENDPOINT env var for exporting traces.
    Gracefully degrades if OpenTelemetry packages not installed.
    """
    from app.core.config import settings

    if not settings.otlp_endpoint:
        logger.info("Tracing disabled (OTLP_ENDPOINT not set)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as e:
        logger.warning(
            "OpenTelemetry packages not installed, tracing disabled",
            error=str(e),
        )
        return

    # Configure resource
    resource = Resource.create({
        "service.name": "mtg-market-intel",
        "service.version": "1.0.0",
        "deployment.environment": settings.environment,
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Configure exporter
    exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Set as global provider
    trace.set_tracer_provider(provider)

    # Instrument libraries
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    # Note: CeleryInstrumentor should be called in the Celery app, not here

    logger.info(
        "Tracing enabled",
        endpoint=settings.otlp_endpoint,
        environment=settings.environment,
    )
