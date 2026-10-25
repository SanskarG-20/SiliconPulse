"""Request-scoped structured logs and optional OpenTelemetry instrumentation."""
from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .settings import settings

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_var.get()),
        }
        for key in ("model", "operation", "input_tokens", "output_tokens", "token_source", "cost_usd", "latency_ms", "status", "ingestion_lag_seconds"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


def install_tracing(app) -> None:
    """Instrument FastAPI and export spans only when an OTLP endpoint is configured."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        if settings.otel_exporter_otlp_endpoint:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(resource=Resource.create({"service.name": settings.otel_service_name}))
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)))
            trace.set_tracer_provider(provider)
    except ImportError:
        logging.getLogger(__name__).warning("OpenTelemetry packages unavailable; tracing disabled")


def record_llm_call(*, model: str, operation: str, input_tokens: int, output_tokens: int, latency_ms: float, status: str, token_source: str = "estimated") -> None:
    input_rate = settings.gemini_input_cost_usd_per_million
    output_rate = settings.gemini_output_cost_usd_per_million
    cost = None
    if input_rate is not None and output_rate is not None:
        cost = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
    logging.getLogger("siliconpulse.llm").info(
        "LLM call completed", extra={
            "model": model, "operation": operation, "input_tokens": input_tokens,
            "output_tokens": output_tokens, "token_source": token_source,
            "cost_usd": cost, "latency_ms": round(latency_ms, 2), "status": status,
        },
    )
    try:
        from opentelemetry import trace

        span = trace.get_tracer("siliconpulse.llm").start_span("llm.call")
        span.set_attributes({
            "llm.model": model,
            "llm.operation": operation,
            "llm.input_tokens": input_tokens,
            "llm.output_tokens": output_tokens,
            "llm.latency_ms": latency_ms,
            "llm.status": status,
            "llm.cost_usd": cost if cost is not None else -1.0,
        })
        span.end()
    except Exception:
        pass


_ingestion_lag_seconds: float | None = None


def set_ingestion_lag_metric(seconds: float | None) -> None:
    """Update an OTel observable gauge when tracing metrics are configured."""
    global _ingestion_lag_seconds
    _ingestion_lag_seconds = seconds
    try:
        from opentelemetry import metrics

        gauge = getattr(set_ingestion_lag_metric, "_gauge", None)
        if gauge is None:
            from opentelemetry.metrics import Observation
            meter = metrics.get_meter("siliconpulse.ingestion")
            gauge = meter.create_observable_gauge(
                "siliconpulse.ingestion.lag.seconds",
                callbacks=[lambda options: [Observation(_ingestion_lag_seconds)] if _ingestion_lag_seconds is not None else []],
                description="Seconds since the most recently ingested signal",
            )
            setattr(set_ingestion_lag_metric, "_gauge", gauge)
    except (ImportError, Exception):
        return


def new_request_id(candidate: str | None = None) -> str:
    value = (candidate or "").strip()
    if value and len(value) <= 128 and all(ch.isalnum() or ch in "._-" for ch in value):
        return value
    return str(uuid.uuid4())


def ingestion_lag_seconds(events: list[dict], now: datetime | None = None) -> float | None:
    if not events or not events[0].get("timestamp"):
        return None
    try:
        stamp = datetime.fromisoformat(str(events[0]["timestamp"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return max(0.0, (current - stamp.astimezone(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


def start_timer() -> float:
    return time.perf_counter()
