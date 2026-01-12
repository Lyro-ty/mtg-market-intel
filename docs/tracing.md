# Distributed Tracing Setup

MTG Market Intel uses OpenTelemetry for distributed tracing.

## Overview

Tracing is **disabled by default**. Set `OTLP_ENDPOINT` to enable.

When enabled, traces are collected for:
- FastAPI HTTP requests
- SQLAlchemy database queries
- Redis operations
- HTTPX outgoing requests

## Local Development (Jaeger)

Start Jaeger:
```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
```

Add to `.env`:
```
OTLP_ENDPOINT=http://localhost:4317
ENVIRONMENT=development
```

View traces at http://localhost:16686

## Production

Configure `OTLP_ENDPOINT` to your tracing backend (Jaeger, Tempo, Datadog, etc.)

## Required Packages

If not already installed:
```bash
pip install opentelemetry-api opentelemetry-sdk \
  opentelemetry-exporter-otlp \
  opentelemetry-instrumentation-fastapi \
  opentelemetry-instrumentation-sqlalchemy \
  opentelemetry-instrumentation-redis \
  opentelemetry-instrumentation-httpx
```
