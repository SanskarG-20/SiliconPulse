"""
Storage module for SiliconPulse backend.
SQLite is a local-development fallback; production state is kept in Supabase Postgres.
"""
from __future__ import annotations

import logging
import hashlib
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread-local storage for SQLite connections
local_storage = threading.local()

def get_db_connection():
    """Get thread-local database connection"""
    from .supabase_client import is_supabase_enabled

    if is_supabase_enabled():
        raise RuntimeError("SQLite is disabled when Supabase/Postgres is configured")
    if settings.app_env.lower() == "production":
        raise RuntimeError("SQLite is a local-development fallback; configure Supabase in production")
    if not hasattr(local_storage, "connection"):
        db_path = Path(settings.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        local_storage.connection = sqlite3.connect(str(db_path), check_same_thread=False)
        local_storage.connection.row_factory = sqlite3.Row
    return local_storage.connection

def init_db():
    """Initialize SQLite only when running without the canonical hosted store."""
    from .supabase_client import is_supabase_enabled

    if is_supabase_enabled():
        return
    if settings.app_env.lower() == "production":
        raise RuntimeError("Supabase/Postgres is required in production")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Table for seen events (deduplication)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT,
                source TEXT,
                title TEXT
            )
        """)

        # Table for source checkpoints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_checkpoints (
                source TEXT PRIMARY KEY,
                last_checkpoint TEXT,
                last_pull_ts TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS websocket_tickets (
                ticket_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )
        """)

        conn.commit()
        logger.info(f"Database initialized at {settings.db_path}")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't raise, just log - we'll handle connection errors gracefully in other functions


def create_websocket_ticket(user_id: str, ttl_seconds: int = 60) -> str:
    """Create an opaque short-lived ticket; only its hash is stored."""
    if not user_id:
        raise ValueError("user_id is required")
    ticket = secrets.token_urlsafe(32)
    ticket_hash = hashlib.sha256(ticket.encode()).hexdigest()
    expires_at = int(datetime.now(timezone.utc).timestamp()) + max(1, min(ttl_seconds, 120))
    from .supabase_client import get_supabase_client, is_supabase_enabled

    if is_supabase_enabled():
        client = get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase is unavailable")
        expiry = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
        client.table("websocket_tickets").delete().lt(
            "expires_at", datetime.now(timezone.utc).isoformat()
        ).execute()
        client.table("websocket_tickets").insert(
            {"ticket_hash": ticket_hash, "user_id": user_id, "expires_at": expiry}
        ).execute()
        return ticket
    conn = get_db_connection()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS websocket_tickets (ticket_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at INTEGER NOT NULL)"
    )
    conn.execute("DELETE FROM websocket_tickets WHERE expires_at <= ?", (int(datetime.now(timezone.utc).timestamp()),))
    conn.execute(
        "INSERT INTO websocket_tickets (ticket_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (ticket_hash, user_id, expires_at),
    )
    conn.commit()
    return ticket


def consume_websocket_ticket(ticket: str) -> str | None:
    """Atomically redeem one ticket exactly once; delete expired tickets too."""
    if not ticket or len(ticket) > 200:
        return None
    ticket_hash = hashlib.sha256(ticket.encode()).hexdigest()
    from .supabase_client import get_supabase_client, is_supabase_enabled

    if is_supabase_enabled():
        client = get_supabase_client()
        if client is None:
            return None
        result = client.rpc("consume_websocket_ticket", {"p_ticket_hash": ticket_hash}).execute()
        data = result.data
        if isinstance(data, str):
            return data
        if isinstance(data, list) and data:
            row = data[0]
            if isinstance(row, dict):
                return row.get("consume_websocket_ticket") or row.get("user_id")
            return str(row) if row else None
        return None
    conn = get_db_connection()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS websocket_tickets (ticket_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at INTEGER NOT NULL)"
    )
    now = int(datetime.now(timezone.utc).timestamp())
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT user_id, expires_at FROM websocket_tickets WHERE ticket_hash = ?", (ticket_hash,)
        ).fetchone()
        conn.execute("DELETE FROM websocket_tickets WHERE ticket_hash = ?", (ticket_hash,))
        conn.commit()
        if row and row["expires_at"] > now:
            return str(row["user_id"])
        return None
    except Exception:
        conn.rollback()
        raise

def is_duplicate(event_id: str) -> bool:
    """Check if an event_id has already been seen"""
    if not settings.dedup_enabled:
        return False

    from .supabase_client import get_supabase_client, is_supabase_enabled

    if is_supabase_enabled():
        client = get_supabase_client()
        if client is None:
            # Fail closed: do not treat unavailable canonical storage as a new event.
            return True
        try:
            result = client.table("market_signals").select("event_id").eq("event_id", event_id).limit(1).execute()
            return bool(result.data)
        except Exception as e:
            logger.error("Canonical signal lookup failed: %s", e)
            return True

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM seen_events WHERE event_id = ?", (event_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking duplicate: {e}")
        return False

def mark_seen(event_id: str, source: str, title: str) -> None:
    """Mark an event as seen"""
    if not settings.dedup_enabled:
        return

    from .supabase_client import is_supabase_enabled

    if is_supabase_enabled():
        # The market_signals primary key is the durable dedup record. New events
        # are inserted atomically by signal_store.insert_events().
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        cursor.execute(
            "INSERT OR IGNORE INTO seen_events (event_id, first_seen_ts, source, title) VALUES (?, ?, ?, ?)",
            (event_id, now, source, title)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error marking event as seen: {e}")

def get_checkpoint(source: str) -> str | None:
    """Get the last checkpoint (timestamp or ID) for a source"""
    if not settings.checkpoint_enabled:
        return None

    from .supabase_client import is_supabase_enabled

    if is_supabase_enabled():
        try:
            from .services.signal_store import get_checkpoint as get_remote_checkpoint

            return get_remote_checkpoint(source)
        except Exception as e:
            logger.error("Canonical checkpoint lookup failed for %s: %s", source, e)
            return None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT last_checkpoint FROM source_checkpoints WHERE source = ?", (source,))
        row = cursor.fetchone()
        return row["last_checkpoint"] if row else None
    except Exception as e:
        logger.error(f"Error getting checkpoint for {source}: {e}")
        return None

def update_checkpoint(source: str, checkpoint: str) -> None:
    """Update the checkpoint for a source"""
    if not settings.checkpoint_enabled:
        return

    from .supabase_client import is_supabase_enabled

    if is_supabase_enabled():
        try:
            from .services.signal_store import set_checkpoint

            set_checkpoint(source, checkpoint)
        except Exception as e:
            logger.error("Canonical checkpoint update failed for %s: %s", source, e)
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        cursor.execute(
            """
            INSERT INTO source_checkpoints (source, last_checkpoint, last_pull_ts)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                last_checkpoint = excluded.last_checkpoint,
                last_pull_ts = excluded.last_pull_ts
            """,
            (source, checkpoint, now)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating checkpoint for {source}: {e}")

def cleanup_old_events(days: int = 30) -> int:
    """Remove events older than N days from seen_events table"""
    from .supabase_client import is_supabase_enabled

    if is_supabase_enabled():
        return 0  # signal IDs are retained with their canonical market_signals rows
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_date,))
        deleted_count = cursor.rowcount
        conn.commit()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old events from dedup store")

        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up old events: {e}")
        return 0


def seen_count() -> int:
    """Count canonical signal IDs in production or local dedup rows in dev."""
    from .supabase_client import is_supabase_enabled

    if is_supabase_enabled():
        try:
            from .services.signal_store import count_events

            return count_events()
        except Exception as e:
            logger.error("Canonical signal count failed: %s", e)
            return -1
    try:
        return int(get_db_connection().execute("SELECT COUNT(*) FROM seen_events").fetchone()[0])
    except Exception:
        return -1
