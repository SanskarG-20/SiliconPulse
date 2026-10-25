"""Atomic daily LLM token budget and per-user call quotas."""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from ..settings import settings


class LLMBudgetExceeded(RuntimeError):
    """The daily global or per-user LLM allowance is exhausted."""


class LLMBudgetUnavailable(RuntimeError):
    """The shared budget store is unavailable in production."""


@dataclass
class Reservation:
    tokens: int
    global_key: str
    redis_client: object | None = None
    local_day: str | None = None


_lock = threading.Lock()
_local_day = ""
_local_tokens = 0
_local_user_calls: dict[str, int] = {}
_redis_client = None
_redis_checked = False

_RESERVE_SCRIPT = """
local global_tokens = tonumber(redis.call('GET', KEYS[1]) or '0')
local user_calls = 0
if ARGV[5] == '1' then user_calls = tonumber(redis.call('GET', KEYS[2]) or '0') end
if global_tokens + tonumber(ARGV[1]) > tonumber(ARGV[2]) then return 0 end
if ARGV[5] == '1' and user_calls + 1 > tonumber(ARGV[3]) then return 0 end
redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[4])
if ARGV[5] == '1' then
  redis.call('INCR', KEYS[2])
  redis.call('EXPIRE', KEYS[2], ARGV[4])
end
return 1
"""


def _today() -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 86400
    return now.date().isoformat(), max(60, int(tomorrow - now.timestamp()))


def _client():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    with _lock:
        if not _redis_checked:
            from ..job_lock import create_redis_client
            _redis_client = create_redis_client(required=settings.app_env.lower() == "production")
            _redis_checked = True
    return _redis_client


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text or "") / 4))


def reserve(user_id: str | None, estimated_tokens: int) -> Reservation:
    """Reserve tokens and one user call atomically before contacting Gemini."""
    global _local_day, _local_tokens, _local_user_calls
    tokens = max(1, int(estimated_tokens))
    day, ttl = _today()
    client = _client()
    global_key = f"siliconpulse:llm:tokens:{day}"
    if client is not None:
        user_key = f"siliconpulse:llm:user-calls:{day}:{user_id}" if user_id else f"siliconpulse:llm:unused:{day}"
        try:
            accepted = client.eval(
                _RESERVE_SCRIPT, 2, global_key, user_key, tokens,
                max(1, settings.llm_daily_token_budget), max(1, settings.llm_user_daily_calls), ttl,
                1 if user_id else 0,
            )
        except Exception as exc:
            if settings.app_env.lower() == "production":
                raise LLMBudgetUnavailable("Shared LLM budget store unavailable") from exc
            accepted = None
        if accepted is None:
            client = None
        elif int(accepted) != 1:
            raise LLMBudgetExceeded("Daily LLM budget or per-user quota exceeded")
        else:
            return Reservation(tokens=tokens, global_key=global_key, redis_client=client)

    if settings.app_env.lower() == "production":
        raise LLMBudgetUnavailable("Redis is required for production LLM budgets")
    with _lock:
        if _local_day != day:
            _local_day, _local_tokens, _local_user_calls = day, 0, {}
        user_calls = _local_user_calls.get(user_id, 0) if user_id else 0
        if _local_tokens + tokens > max(1, settings.llm_daily_token_budget):
            raise LLMBudgetExceeded("Daily LLM token budget exceeded")
        if user_id and user_calls >= max(1, settings.llm_user_daily_calls):
            raise LLMBudgetExceeded("Per-user daily LLM quota exceeded")
        _local_tokens += tokens
        if user_id:
            _local_user_calls[user_id] = user_calls + 1
    return Reservation(tokens=tokens, global_key=global_key, local_day=day)


def settle(reservation: Reservation, actual_tokens: int | None) -> None:
    """Release unused reserved tokens; failed/unknown calls remain charged conservatively."""
    if actual_tokens is None:
        return
    refund = max(0, reservation.tokens - max(0, int(actual_tokens)))
    if not refund:
        return
    if reservation.redis_client is not None:
        try:
            reservation.redis_client.decrby(reservation.global_key, refund)
        except Exception:
            return
    elif reservation.local_day == _local_day:
        global _local_tokens
        with _lock:
            _local_tokens = max(0, _local_tokens - refund)


def reset_for_tests() -> None:
    global _local_day, _local_tokens, _local_user_calls, _redis_client, _redis_checked
    with _lock:
        _local_day, _local_tokens, _local_user_calls = "", 0, {}
        _redis_client, _redis_checked = None, False
