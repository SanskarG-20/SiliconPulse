from __future__ import annotations

# pyright: reportMissingImports=false
import logging
from typing import Any

from .settings import settings

logger = logging.getLogger(__name__)

_supabase_client: Any | None = None
_supabase_failed = False


def is_supabase_enabled() -> bool:
    url = (settings.supabase_url or "").strip()
    key = (settings.supabase_service_role_key or "").strip()
    placeholder_tokens = ("your-", "your_", "example", "placeholder")
    if not url or not key:
        return False
    if any(token in url.lower() for token in placeholder_tokens):
        return False
    if any(token in key.lower() for token in placeholder_tokens):
        return False
    return True


def get_supabase_client() -> Any | None:
    """
    Service-role client (bypasses RLS). Used for server-side writes.
    RLS is enforced for direct client access via anon key; see migration 001_rls.sql.
    """
    global _supabase_client, _supabase_failed

    if _supabase_client is not None:
        return _supabase_client
    if _supabase_failed:
        return None

    if not is_supabase_enabled():
        return None

    try:
        from supabase import create_client
    except Exception as exc:
        logger.warning("Supabase package import failed: %s", exc)
        return None

    try:
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        return _supabase_client
    except Exception as exc:
        logger.warning("Supabase client initialization failed: %s", exc)
        _supabase_failed = True
        return None


def get_user_scoped_client(jwt: str) -> Any | None:
    """
    Per-user client that respects RLS (requires SUPABASE_ANON_KEY + valid Clerk JWT).
    Returns None if anon key not configured. Useful if you later expose Supabase
    directly to the frontend with RLS. Currently backend uses service_role for writes.
    """
    if not is_supabase_enabled():
        return None
    anon = (settings.supabase_anon_key or "").strip()
    if not anon:
        return None
    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, anon)
        # Supabase-py will send Authorization: Bearer <jwt> if you set auth
        try:
            client.auth.set_session(access_token=jwt, refresh_token="")  # type: ignore
        except Exception:
            pass
        # Fallback: inject header manually for postgrest
        try:
            client.postgrest.auth(jwt)  # type: ignore
        except Exception:
            pass
        return client
    except Exception as exc:
        logger.debug(f"User-scoped Supabase client failed: {exc}")
        return None


def ensure_user(user_id: str, email: str | None = None) -> bool:
    """
    Ensure user exists in Supabase.
    Creates user if not exists, updates email if provided.
    Returns True if successful, False otherwise.
    """
    client = get_supabase_client()
    if client is None:
        logger.warning("Supabase client not initialized - skipping user creation")
        return False

    if not user_id:
        logger.warning("ensure_user called with empty user_id")
        return False

    payload: dict[str, Any] = {"id": user_id}
    if email:
        payload["email"] = email

    try:
        logger.debug(f"Upserting user {user_id} with payload {payload}")
        response = client.table("users").upsert(payload, on_conflict="id").execute()

        if response.data:
            logger.info(f"✓ User {user_id} successfully synced to Supabase (email: {email})")
            return True
        else:
            logger.warning(f"Supabase upsert for user {user_id} returned empty data")
            return False

    except Exception as exc:
        logger.error(f"✗ Supabase ensure_user failed for {user_id}: {exc}", exc_info=True)
        return False


def insert_query_record(
    user_id: str,
    query_text: str,
    k: int,
    evidence_count: int,
    signal_strength: int,
) -> str | None:
    client = get_supabase_client()
    if client is None:
        return None

    try:
        response = (
            client.table("queries")
            .insert(
                {
                    "user_id": user_id,
                    "query_text": query_text,
                    "k": k,
                    "evidence_count": evidence_count,
                    "signal_strength": signal_strength,
                }
            )
            .execute()
        )

        data = response.data or []
        if data and isinstance(data, list):
            row_id = data[0].get("id")
            if row_id:
                logger.info(f"✓ Query record {row_id} stored for user {user_id}")
                return str(row_id)

        logger.warning(f"Query insert returned empty data for user {user_id}")
        return None
    except Exception as exc:
        logger.error(f"✗ Supabase insert_query_record failed for user {user_id}: {exc}", exc_info=True)

    return None


def insert_insight_record(
    user_id: str,
    query_text: str,
    insight: str,
    model_name: str,
    status: str,
    query_id: str | None = None,
) -> str | None:
    client = get_supabase_client()
    if client is None:
        return None

    payload: dict[str, Any] = {
        "user_id": user_id,
        "query_text": query_text,
        "insight": insight,
        "model_name": model_name,
        "status": status,
    }

    if query_id:
        payload["query_id"] = query_id

    try:
        response = client.table("insights").insert(payload).execute()
        data = response.data or []
        if data and isinstance(data, list):
            row_id = data[0].get("id")
            if row_id:
                logger.info(f"✓ Insight record {row_id} stored for user {user_id} (status={status})")
                return str(row_id)

        logger.warning(f"Insight insert returned empty data for user {user_id}")
        return None
    except Exception as exc:
        logger.error(f"✗ Supabase insert_insight_record failed for user {user_id}: {exc}", exc_info=True)

    return None


def list_watchlist(user_id: str) -> list[str]:
    """Return watchlisted companies for user (empty when Supabase disabled)."""
    client = get_supabase_client()
    if client is None or not user_id:
        return []
    try:
        resp = client.table("watchlists").select("company").eq("user_id", user_id).order("created_at").execute()
        return [r.get("company") for r in (resp.data or []) if r.get("company")]
    except Exception as exc:
        logger.debug(f"list_watchlist failed for {user_id}: {exc}")
        return []


def add_watchlist_company(user_id: str, company: str) -> bool:
    client = get_supabase_client()
    if client is None or not user_id or not company:
        return False
    try:
        client.table("watchlists").upsert(
            {"user_id": user_id, "company": company.strip()[:100]}, on_conflict="user_id,company"
        ).execute()
        return True
    except Exception as exc:
        logger.debug(f"add_watchlist failed for {user_id}/{company}: {exc}")
        return False


def remove_watchlist_company(user_id: str, company: str) -> bool:
    client = get_supabase_client()
    if client is None or not user_id or not company:
        return False
    try:
        client.table("watchlists").delete().eq("user_id", user_id).eq("company", company).execute()
        return True
    except Exception as exc:
        logger.debug(f"remove_watchlist failed for {user_id}/{company}: {exc}")
        return False


def list_user_history(user_id: str, kind: str = "queries", limit: int = 10) -> list[dict]:
    """List recent queries or insights for history UI. Returns [] when disabled."""
    client = get_supabase_client()
    if client is None or not user_id:
        return []
    table = "insights" if kind == "insights" else "queries"
    try:
        resp = (
            client.table(table).select("*").eq("user_id", user_id).order("created_at", desc=True).limit(max(1, min(limit, 25))).execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.debug(f"list_user_history({table}) failed for {user_id}: {exc}")
        return []


def create_brief(
    user_id: str, query_text: str, insight: str, evidence: list[dict] | None = None, workspace_id: str | None = None
) -> str | None:
    client = get_supabase_client()
    if client is None or not user_id:
        return None
    payload: dict[str, Any] = {
        "user_id": user_id,
        "query_text": query_text[:500],
        "insight": insight[:50000],
        "evidence": evidence or [],
        "is_public": True,
    }
    if workspace_id:
        payload["workspace_id"] = workspace_id
    try:
        resp = client.table("briefs").insert(payload).execute()
        data = resp.data or []
        if data and isinstance(data, list):
            return str(data[0].get("id")) if data[0].get("id") else None
        return None
    except Exception as exc:
        # workspace_id column may not exist if 006 not applied yet — retry without it
        if workspace_id:
            try:
                payload.pop("workspace_id", None)
                resp = client.table("briefs").insert(payload).execute()
                data = resp.data or []
                if data and isinstance(data, list):
                    return str(data[0].get("id")) if data[0].get("id") else None
                return None
            except Exception as exc2:
                logger.debug(f"create_brief retry failed for {user_id}: {exc2}")
                return None
        logger.debug(f"create_brief failed for {user_id}: {exc}")
        return None


def get_brief(brief_id: str) -> dict | None:
    client = get_supabase_client()
    if client is None or not brief_id:
        return None
    try:
        resp = client.table("briefs").select("*").eq("id", brief_id).single().execute()
        return resp.data if resp.data else None
    except Exception as exc:
        logger.debug(f"get_brief failed for {brief_id}: {exc}")
        return None


def list_briefs(user_id: str, limit: int = 10) -> list[dict]:
    client = get_supabase_client()
    if client is None or not user_id:
        return []
    try:
        resp = client.table("briefs").select("id,query_text,created_at").eq("user_id", user_id).order("created_at", desc=True).limit(max(1, min(limit, 25))).execute()
        return resp.data or []
    except Exception as exc:
        logger.debug(f"list_briefs failed for {user_id}: {exc}")
        return []


def get_digest_prefs(user_id: str) -> dict | None:
    client = get_supabase_client()
    if client is None or not user_id:
        return None
    try:
        resp = client.table("digest_prefs").select("*").eq("user_id", user_id).single().execute()
        return resp.data if resp.data else None
    except Exception as exc:
        logger.debug(f"get_digest_prefs failed for {user_id}: {exc}")
        return None


def upsert_digest_prefs(
    user_id: str,
    enabled: bool,
    hour_utc: int,
    email: str | None = None,
    webhook_url: str | None = None,
) -> dict | None:
    client = get_supabase_client()
    if client is None or not user_id:
        return None
    try:
        payload: dict[str, Any] = {
            "user_id": user_id,
            "enabled": bool(enabled),
            "hour_utc": max(0, min(23, int(hour_utc))),
            "email": (email or "").strip()[:254] or None,
            "webhook_url": (webhook_url or "").strip()[:500] or None,
        }
        resp = client.table("digest_prefs").upsert(payload, on_conflict="user_id").execute()
        data = resp.data or []
        return data[0] if data else payload
    except Exception as exc:
        logger.debug(f"upsert_digest_prefs failed for {user_id}: {exc}")
        return None


def list_due_digest_prefs(hour_utc: int) -> list[dict]:
    """Return elapsed digests and previous-day misses for catch-up after downtime."""
    client = get_supabase_client()
    if client is None:
        return []
    try:
        resp = client.table("digest_prefs").select("*").eq("enabled", True).execute()
        rows = resp.data or []
        today = __import__("datetime").datetime.utcnow().date().isoformat()
        due = []
        for r in rows:
            last = (r.get("last_sent_at") or "")[:10]
            try:
                scheduled_hour = int(r.get("hour_utc", 0))
            except (TypeError, ValueError):
                continue
            created = (r.get("created_at") or today)[:10]
            missed_prior_day = (last and last < today) or (not last and created < today)
            if (
                last != today
                and (missed_prior_day or scheduled_hour <= hour_utc)
                and (r.get("email") or r.get("webhook_url"))
            ):
                due.append(r)
        return due
    except Exception as exc:
        logger.debug(f"list_due_digest_prefs failed: {exc}")
        return []


def mark_digest_sent(user_id: str) -> None:
    client = get_supabase_client()
    if client is None or not user_id:
        return
    try:
        from datetime import datetime, timezone

        client.table("digest_prefs").update({"last_sent_at": datetime.now(timezone.utc).isoformat()}).eq("user_id", user_id).execute()
    except Exception as exc:
        logger.debug(f"mark_digest_sent failed for {user_id}: {exc}")


def create_api_key(user_id: str, name: str, key_hash: str, key_prefix: str, scopes: list[str] | None = None, expires_at: str | None = None) -> dict | None:
    client = get_supabase_client()
    if client is None or not user_id:
        return None
    try:
        resp = client.table("api_keys").insert({"user_id": user_id, "name": name[:80], "key_hash": key_hash, "key_prefix": key_prefix, "scopes": scopes or ["signals:read", "query:read", "trends:read", "compare:read", "reports:generate"], "expires_at": expires_at}).execute()
        data = resp.data or []
        return data[0] if data else None
    except Exception as exc:
        logger.debug(f"create_api_key failed for {user_id}: {exc}")
        return None


def list_api_keys(user_id: str) -> list[dict]:
    client = get_supabase_client()
    if client is None or not user_id:
        return []
    try:
        resp = client.table("api_keys").select("id,name,key_prefix,scopes,expires_at,revoked,last_used_at,created_at").eq("user_id", user_id).order("created_at", desc=True).execute()
        return resp.data or []
    except Exception as exc:
        logger.debug(f"list_api_keys failed for {user_id}: {exc}")
        return []


def revoke_api_key(user_id: str, key_id: str) -> bool:
    client = get_supabase_client()
    if client is None or not user_id:
        return False
    try:
        client.table("api_keys").update({"revoked": True}).eq("id", key_id).eq("user_id", user_id).execute()
        return True
    except Exception as exc:
        logger.debug(f"revoke_api_key failed for {key_id}: {exc}")
        return False


def rotate_api_key(user_id: str, key_id: str, key_hash: str, key_prefix: str, expires_at: str) -> dict | None:
    """Atomically revoke an owned key and issue its replacement."""
    client = get_supabase_client()
    if client is None or not user_id:
        return None
    try:
        resp = client.rpc("rotate_user_api_key", {
            "p_user_id": user_id,
            "p_old_key_id": key_id,
            "p_key_hash": key_hash,
            "p_key_prefix": key_prefix,
            "p_expires_at": expires_at,
        }).execute()
        rows = resp.data or []
        return rows[0] if rows and isinstance(rows[0], dict) else None
    except Exception as exc:
        logger.debug("rotate_api_key failed for %s: %s", key_id, exc)
        return None


def lookup_api_key(key_hash: str) -> dict | None:
    """Service-role lookup for API-key auth fallback. Returns row or None."""
    client = get_supabase_client()
    if client is None or not key_hash:
        return None
    try:
        resp = client.table("api_keys").select("id,user_id,revoked,scopes,expires_at").eq("key_hash", key_hash).eq("revoked", False).single().execute()
        return resp.data if resp.data else None
    except Exception as exc:
        logger.debug(f"lookup_api_key failed: {exc}")
        return None


def touch_api_key(key_id: str) -> None:
    client = get_supabase_client()
    if client is None or not key_id:
        return
    try:
        client.table("api_keys").update({"last_used_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"}).eq("id", key_id).execute()
    except Exception as exc:
        logger.debug(f"touch_api_key failed for {key_id}: {exc}")


def list_team_webhooks(user_id: str) -> list[dict]:
    client = get_supabase_client()
    if client is None or not user_id:
        return []
    try:
        resp = client.table("team_webhooks").select("id,url,events,enabled,last_sent_at,created_at").eq("user_id", user_id).order("created_at", desc=True).execute()
        rows = resp.data or []
        # Redact URL to host for list views
        for r in rows:
            try:
                from urllib.parse import urlparse

                r["url_host"] = urlparse(r.get("url", "")).hostname or ""
                r["url"] = ""
            except Exception:
                r["url_host"] = ""
        return rows
    except Exception as exc:
        logger.debug(f"list_team_webhooks failed for {user_id}: {exc}")
        return []


def add_team_webhook(user_id: str, url: str, events: list[str]) -> dict | None:
    client = get_supabase_client()
    if client is None or not user_id:
        return None
    try:
        resp = client.table("team_webhooks").insert({"user_id": user_id, "url": url[:500], "events": events, "enabled": True}).execute()
        data = resp.data or []
        return data[0] if data else None
    except Exception as exc:
        logger.debug(f"add_team_webhook failed for {user_id}: {exc}")
        return None


def delete_team_webhook(user_id: str, webhook_id: str) -> bool:
    client = get_supabase_client()
    if client is None or not user_id:
        return False
    try:
        client.table("team_webhooks").delete().eq("id", webhook_id).eq("user_id", user_id).execute()
        return True
    except Exception as exc:
        logger.debug(f"delete_team_webhook failed for {webhook_id}: {exc}")
        return False


def list_enabled_spike_webhooks() -> list[dict]:
    """All enabled webhooks subscribed to spike.alert (service-role, for cron)."""
    client = get_supabase_client()
    if client is None:
        return []
    try:
        resp = client.table("team_webhooks").select("*").eq("enabled", True).execute()
        rows = [r for r in (resp.data or []) if "spike.alert" in (r.get("events") or []) and r.get("url")]
        today = __import__("datetime").datetime.utcnow().date().isoformat()
        return [r for r in rows if (r.get("last_sent_at") or "")[:10] != today]
    except Exception as exc:
        logger.debug(f"list_enabled_spike_webhooks failed: {exc}")
        return []


def mark_webhook_sent(webhook_id: str) -> None:
    client = get_supabase_client()
    if client is None or not webhook_id:
        return
    try:
        client.table("team_webhooks").update({"last_sent_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"}).eq("id", webhook_id).execute()
    except Exception as exc:
        logger.debug(f"mark_webhook_sent failed for {webhook_id}: {exc}")


def list_brief_comments(brief_id: str, limit: int = 50) -> list[dict]:
    client = get_supabase_client()
    if client is None or not brief_id:
        return []
    try:
        resp = client.table("brief_comments").select("id,user_id,body,created_at").eq("brief_id", brief_id).order("created_at").limit(max(1, min(limit, 100))).execute()
        return resp.data or []
    except Exception as exc:
        logger.debug(f"list_brief_comments failed for {brief_id}: {exc}")
        return []


def add_brief_comment(brief_id: str, user_id: str, body: str) -> dict | None:
    client = get_supabase_client()
    if client is None or not brief_id or not user_id:
        return None
    try:
        resp = client.table("brief_comments").insert({"brief_id": brief_id, "user_id": user_id, "body": body[:2000]}).execute()
        data = resp.data or []
        return data[0] if data else None
    except Exception as exc:
        logger.debug(f"add_brief_comment failed for {brief_id}: {exc}")
        return None


def delete_brief_comment(comment_id: str, user_id: str) -> bool:
    """Delete only if the row belongs to the user (service role bypasses RLS, so enforce here)."""
    client = get_supabase_client()
    if client is None or not comment_id or not user_id:
        return False
    try:
        client.table("brief_comments").delete().eq("id", comment_id).eq("user_id", user_id).execute()
        return True
    except Exception as exc:
        logger.debug(f"delete_brief_comment failed for {comment_id}: {exc}")
        return False


def create_workspace(owner_id: str, name: str, invite_code: str) -> dict | None:
    client = get_supabase_client()
    if client is None or not owner_id:
        return None
    try:
        resp = client.table("workspaces").insert({"owner_id": owner_id, "name": name[:120], "invite_code": invite_code}).execute()
        data = resp.data or []
        if not data:
            return None
        ws = data[0]
        try:
            client.table("workspace_members").upsert(
                {"workspace_id": ws["id"], "user_id": owner_id, "role": "owner"}, on_conflict="workspace_id,user_id"
            ).execute()
        except Exception:
            pass
        return ws
    except Exception as exc:
        logger.debug(f"create_workspace failed for {owner_id}: {exc}")
        return None


def list_workspaces(user_id: str) -> list[dict]:
    """Workspaces owned or joined by the user."""
    client = get_supabase_client()
    if client is None or not user_id:
        return []
    try:
        owned = client.table("workspaces").select("id,name,owner_id,invite_code,created_at").eq("owner_id", user_id).execute()
        mem = client.table("workspace_members").select("workspace_id").eq("user_id", user_id).execute()
        joined_ids = [r.get("workspace_id") for r in (mem.data or [])]
        joined = []
        if joined_ids:
            joined = client.table("workspaces").select("id,name,owner_id,invite_code,created_at").in_("id", joined_ids).execute().data or []
        seen, out = set(), []
        for r in (owned.data or []) + joined:
            if r.get("id") not in seen:
                seen.add(r["id"])
                out.append(r)
        return out
    except Exception as exc:
        logger.debug(f"list_workspaces failed for {user_id}: {exc}")
        return []


def is_workspace_member(user_id: str, workspace_id: str) -> bool:
    client = get_supabase_client()
    if client is None or not user_id or not workspace_id:
        return False
    try:
        ws = client.table("workspaces").select("id,owner_id").eq("id", workspace_id).single().execute()
        if ws.data and ws.data.get("owner_id") == user_id:
            return True
        mem = client.table("workspace_members").select("workspace_id").eq("workspace_id", workspace_id).eq("user_id", user_id).execute()
        return bool(mem.data)
    except Exception as exc:
        logger.debug(f"is_workspace_member failed: {exc}")
        return False


def join_workspace(user_id: str, invite_code: str) -> dict | None:
    client = get_supabase_client()
    if client is None or not user_id or not invite_code:
        return None
    try:
        ws = client.table("workspaces").select("id,name").eq("invite_code", invite_code.strip()).single().execute()
        if not ws.data:
            return None
        client.table("workspace_members").upsert(
            {"workspace_id": ws.data["id"], "user_id": user_id, "role": "member"}, on_conflict="workspace_id,user_id"
        ).execute()
        return ws.data
    except Exception as exc:
        logger.debug(f"join_workspace failed: {exc}")
        return None


def leave_workspace(user_id: str, workspace_id: str) -> bool:
    client = get_supabase_client()
    if client is None or not user_id:
        return False
    try:
        client.table("workspace_members").delete().eq("workspace_id", workspace_id).eq("user_id", user_id).execute()
        return True
    except Exception as exc:
        logger.debug(f"leave_workspace failed: {exc}")
        return False


def list_workspace_members(workspace_id: str) -> list[dict]:
    client = get_supabase_client()
    if client is None or not workspace_id:
        return []
    try:
        resp = client.table("workspace_members").select("user_id,role,created_at").eq("workspace_id", workspace_id).execute()
        return resp.data or []
    except Exception as exc:
        logger.debug(f"list_workspace_members failed: {exc}")
        return []


def list_workspace_watchlist(workspace_id: str) -> list[str]:
    client = get_supabase_client()
    if client is None or not workspace_id:
        return []
    try:
        resp = client.table("workspace_watchlist").select("company").eq("workspace_id", workspace_id).order("created_at").execute()
        return [r.get("company") for r in (resp.data or []) if r.get("company")]
    except Exception as exc:
        logger.debug(f"list_workspace_watchlist failed: {exc}")
        return []


def add_workspace_company(workspace_id: str, company: str, added_by: str | None = None) -> bool:
    client = get_supabase_client()
    if client is None or not workspace_id or not company:
        return False
    try:
        client.table("workspace_watchlist").upsert(
            {"workspace_id": workspace_id, "company": company.strip()[:100], "added_by": added_by}, on_conflict="workspace_id,company"
        ).execute()
        return True
    except Exception as exc:
        logger.debug(f"add_workspace_company failed: {exc}")
        return False


def remove_workspace_company(workspace_id: str, company: str) -> bool:
    client = get_supabase_client()
    if client is None or not workspace_id:
        return False
    try:
        client.table("workspace_watchlist").delete().eq("workspace_id", workspace_id).eq("company", company).execute()
        return True
    except Exception as exc:
        logger.debug(f"remove_workspace_company failed: {exc}")
        return False


def list_workspace_briefs(workspace_id: str) -> list[dict]:
    client = get_supabase_client()
    if client is None or not workspace_id:
        return []
    try:
        resp = client.table("briefs").select("id,query_text,created_at").eq("workspace_id", workspace_id).order("created_at", desc=True).limit(10).execute()
        return resp.data or []
    except Exception:
        # Column may not exist if 006 not applied yet
        return []


def list_rss_feeds(user_id: str) -> list[dict]:
    client = get_supabase_client()
    if client is None or not user_id:
        return []
    try:
        resp = client.table("rss_feeds").select("id,url,label,enabled,last_fetched_at,last_error,created_at").eq("user_id", user_id).order("created_at").execute()
        return resp.data or []
    except Exception as exc:
        logger.debug(f"list_rss_feeds failed for {user_id}: {exc}")
        return []


def add_rss_feed(user_id: str, url: str, label: str) -> dict | None:
    client = get_supabase_client()
    if client is None or not user_id:
        return None
    try:
        resp = client.table("rss_feeds").insert({"user_id": user_id, "url": url[:500], "label": (label or "")[:120], "enabled": True}).execute()
        data = resp.data or []
        return data[0] if data else None
    except Exception as exc:
        logger.debug(f"add_rss_feed failed: {exc}")
        return None


def delete_rss_feed(user_id: str, feed_id: str) -> bool:
    client = get_supabase_client()
    if client is None or not user_id:
        return False
    try:
        client.table("rss_feeds").delete().eq("id", feed_id).eq("user_id", user_id).execute()
        return True
    except Exception as exc:
        logger.debug(f"delete_rss_feed failed: {exc}")
        return False


def toggle_rss_feed(user_id: str, feed_id: str, enabled: bool) -> bool:
    client = get_supabase_client()
    if client is None or not user_id:
        return False
    try:
        client.table("rss_feeds").update({"enabled": bool(enabled)}).eq("id", feed_id).eq("user_id", user_id).execute()
        return True
    except Exception as exc:
        logger.debug(f"toggle_rss_feed failed: {exc}")
        return False


def list_enabled_rss_feeds(limit: int = 200) -> list[dict]:
    client = get_supabase_client()
    if client is None:
        return []
    try:
        resp = client.table("rss_feeds").select("*").eq("enabled", True).limit(max(1, min(limit, 500))).execute()
        return resp.data or []
    except Exception as exc:
        logger.debug(f"list_enabled_rss_feeds failed: {exc}")
        return []


def touch_rss_feed(feed_id: str, error: str | None = None) -> None:
    client = get_supabase_client()
    if client is None or not feed_id:
        return
    try:
        client.table("rss_feeds").update(
            {"last_fetched_at": __import__("datetime").datetime.utcnow().isoformat() + "Z", "last_error": (error or "")[:300] or None}
        ).eq("id", feed_id).execute()
    except Exception as exc:
        logger.debug(f"touch_rss_feed failed: {exc}")


def insert_signal_record(
    user_id: str,
    source: str,
    title: str,
    content: str,
    timestamp: str,
    company: str | None = None,
    event_type: str | None = None,
    url: str | None = None,
) -> str | None:
    client = get_supabase_client()
    if client is None:
        return None

    payload: dict[str, Any] = {
        "user_id": user_id,
        "source": source,
        "title": title,
        "content": content,
        "event_timestamp": timestamp,
        "company": company,
        "event_type": event_type,
        "url": url,
    }

    try:
        response = client.table("signals").insert(payload).execute()
        data = response.data or []
        if data and isinstance(data, list):
            row_id = data[0].get("id")
            if row_id:
                logger.info(f"✓ Signal record {row_id} stored for user {user_id} (source={source})")
                return str(row_id)

        logger.warning(f"Signal insert returned empty data for user {user_id}")
        return None
    except Exception as exc:
        logger.error(f"✗ Supabase insert_signal_record failed for user {user_id}: {exc}", exc_info=True)

    return None
