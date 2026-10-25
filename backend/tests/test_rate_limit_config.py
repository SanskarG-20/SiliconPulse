import pytest

from app.core import limiter as limiter_module


def test_development_rate_limiter_uses_memory_without_redis():
    assert limiter_module.resolve_storage_uri("development", "") == "memory://"


def test_production_rate_limiter_requires_redis():
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        limiter_module.resolve_storage_uri("production", "")
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        limiter_module.resolve_storage_uri("production", "memory://")
    assert limiter_module.resolve_storage_uri("production", "redis://localhost:6379/0") == "redis://localhost:6379/0"


def test_production_startup_pings_redis(monkeypatch):
    monkeypatch.setattr(limiter_module.settings, "app_env", "production")
    monkeypatch.setattr(limiter_module, "_storage", "redis://localhost:6379/0")
    monkeypatch.setattr("app.job_lock.create_redis_client", lambda required: object())
    limiter_module.validate_rate_limit_store()


def test_production_startup_fails_if_redis_is_unreachable(monkeypatch):
    monkeypatch.setattr(limiter_module.settings, "app_env", "production")
    monkeypatch.setattr(limiter_module, "_storage", "redis://localhost:6379/0")
    def fail(required):
        raise RuntimeError("unreachable")
    monkeypatch.setattr("app.job_lock.create_redis_client", fail)
    with pytest.raises(RuntimeError, match="reachable Redis"):
        limiter_module.validate_rate_limit_store()
    monkeypatch.setattr(limiter_module.settings, "app_env", "development")
