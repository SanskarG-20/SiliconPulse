import json
import logging
from datetime import datetime, timezone

from app.observability import JsonFormatter, ingestion_lag_seconds, new_request_id, record_llm_call
from fastapi.testclient import TestClient
from app.main import app


def test_json_formatter_includes_request_id_and_safe_llm_fields():
    record = logging.LogRecord("test", logging.INFO, "", 1, "LLM call completed", (), None)
    record.request_id = "req-123"
    record.model = "gemini-test"
    record.operation = "generate"
    rendered = json.loads(JsonFormatter().format(record))
    assert rendered["request_id"] == "req-123"
    assert rendered["model"] == "gemini-test"
    assert "message" in rendered


def test_request_id_validation():
    assert new_request_id("request_1") == "request_1"
    generated = new_request_id("invalid id")
    assert len(generated) == 36


def test_request_id_is_returned_to_callers():
    response = TestClient(app).get("/ping", headers={"X-Request-ID": "trace-42"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "trace-42"


def test_ingestion_lag_metric_calculates_seconds_and_handles_missing_data():
    now = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
    assert ingestion_lag_seconds([{"timestamp": "2026-01-01T00:00:00Z"}], now) == 10
    assert ingestion_lag_seconds([], now) is None
    assert ingestion_lag_seconds([{"timestamp": "bad"}], now) is None


def test_llm_log_has_token_latency_and_optional_cost(caplog):
    with caplog.at_level(logging.INFO, logger="siliconpulse.llm"):
        record_llm_call(model="gemini-test", operation="generate", input_tokens=10, output_tokens=4, latency_ms=12.5, status="ok")
    rec = next(item for item in caplog.records if item.name == "siliconpulse.llm")
    assert rec.input_tokens == 10
    assert rec.output_tokens == 4
    assert rec.latency_ms == 12.5
