"""
Storage module for SiliconPulse backend.
Handles SQLite database connections, deduplication persistence, and source checkpointing.
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import threading

from .settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread-local storage for SQLite connections
local_storage = threading.local()

def get_db_connection():
    """Get thread-local database connection"""
    if not hasattr(local_storage, "connection"):
        db_path = Path(settings.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        local_storage.connection = sqlite3.connect(str(db_path), check_same_thread=False)
        local_storage.connection.row_factory = sqlite3.Row
    return local_storage.connection

def init_db():
    """Initialize the SQLite database with required tables"""
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
        
        conn.commit()
        logger.info(f"Database initialized at {settings.db_path}")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't raise, just log - we'll handle connection errors gracefully in other functions

def is_duplicate(event_id: str) -> bool:
    """Check if an event_id has already been seen"""
    if not settings.dedup_enabled:
        return False
        
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

def get_checkpoint(source: str) -> Optional[str]:
    """Get the last checkpoint (timestamp or ID) for a source"""
    if not settings.checkpoint_enabled:
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
