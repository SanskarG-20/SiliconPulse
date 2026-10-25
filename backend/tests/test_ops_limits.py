from datetime import datetime, timedelta

import pytest

from app.query_cache import QueryCache
from app.services import llm_budget


def test_report_cache_normalizes_query_and_invalidates_when_evidence_hash_changes():
    cache = QueryCache(ttl_seconds=10, max_size=2, report_ttl_seconds=300)
    cache.set_report("  NVIDIA   revenue ", "evidence-a", '{"sections":[]}')

    assert cache.get_report("nvidia revenue", "evidence-a") == '{"sections":[]}'
    assert cache.get_report("nvidia revenue", "evidence-b") is None

    key = cache._make_report_key("nvidia revenue", "evidence-a")
    cache.report_cache[key] = ("expired", datetime.utcnow() - timedelta(seconds=301))
    assert cache.get_report("nvidia revenue", "evidence-a") is None


def test_local_llm_budget_enforces_per_user_calls_and_global_token_cap(monkeypatch):
    llm_budget.reset_for_tests()
    monkeypatch.setattr(llm_budget, "_client", lambda: None)
    monkeypatch.setattr(llm_budget.settings, "app_env", "development")
    monkeypatch.setattr(llm_budget.settings, "llm_daily_token_budget", 24)
    monkeypatch.setattr(llm_budget.settings, "llm_user_daily_calls", 2)

    first = llm_budget.reserve("user-a", 8)
    llm_budget.reserve("user-a", 8)
    with pytest.raises(llm_budget.LLMBudgetExceeded, match="quota"):
        llm_budget.reserve("user-a", 1)
    with pytest.raises(llm_budget.LLMBudgetExceeded, match="token budget"):
        llm_budget.reserve("user-b", 9)

    llm_budget.settle(first, 3)
    third = llm_budget.reserve("user-b", 8)
    assert third.tokens == 8
    llm_budget.reset_for_tests()


def test_production_budget_fails_closed_without_redis(monkeypatch):
    llm_budget.reset_for_tests()
    monkeypatch.setattr(llm_budget, "_client", lambda: None)
    monkeypatch.setattr(llm_budget.settings, "app_env", "production")
    with pytest.raises(llm_budget.LLMBudgetUnavailable):
        llm_budget.reserve("user-a", 1)
    monkeypatch.setattr(llm_budget.settings, "app_env", "development")
    llm_budget.reset_for_tests()
