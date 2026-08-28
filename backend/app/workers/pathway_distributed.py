"""
Sharded Pathway runner for horizontal scale.
Each instance handles 1/N of the stream by hashing event_id % shard_count.
Run via: python -m app.workers.pathway_distributed --shard 0 --shards 4
Or via env: SHARD_ID=0 SHARD_COUNT=4 python -m app.workers.pathway_distributed

When shard_count=1, behaves like the original single-process pipeline.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

# Reuse helpers from pathway_pipeline
try:
    from pathway_pipeline import COMPANY_KEYWORDS, EVENT_KEYWORDS, compute_event_id, tag_company, tag_event_type, SignalSchema  # type: ignore

    HAS_PATHWAY_SOURCE = True
except Exception:
    HAS_PATHWAY_SOURCE = False
    COMPANY_KEYWORDS = {}  # type: ignore
    EVENT_KEYWORDS = {}  # type: ignore


def _shard_for(event_id: str, shard_count: int) -> int:
    return int(hashlib.sha256(event_id.encode()).hexdigest()[:8], 16) % shard_count


def run_sharded(shard_id: int = 0, shard_count: int = 1):
    # Only import pathway when actually running (not on Windows CI)
    try:
        import pathway as pw  # type: ignore
    except ImportError as e:
        print(f"Pathway not installed (Windows fallback): {e}")
        print("Use mock_pathway_pipeline for local dev on Windows.")
        return

    import json

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    DATA_DIR = PROJECT_ROOT / "data"
    INPUT_FILE = DATA_DIR / "stream.jsonl"
    OUTPUT_FILE = DATA_DIR / f"pathway_out_{shard_id}.jsonl" if shard_count > 1 else DATA_DIR / "pathway_out.jsonl"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Pathway sharded pipeline shard {shard_id}/{shard_count}")
    print(f"📂 Input: {INPUT_FILE}")
    print(f"📂 Output: {OUTPUT_FILE}")

    # Define schema inline to avoid import cycle
    class ShardSchema(pw.Schema):
        timestamp: str
        source: str
        title: str
        content: str
        url: str = ""
        company: str = "Unknown"
        event_type: str = "general"

    signals = pw.io.jsonl.read(str(INPUT_FILE), schema=ShardSchema, mode="streaming", autocommit_duration_ms=1000)

    # Tag + id
    def _compute_id(title: str, snippet: str, url: str) -> str:
        content = snippet[:200] if snippet else ""
        unique = f"{title.lower().strip()}|{content.lower().strip()}|{url.lower().strip() if url else ''}"
        return hashlib.sha256(unique.encode()).hexdigest()

    def _tag_company(title: str, content: str, existing: str) -> str:
        if existing and existing.lower() != "unknown":
            return existing
        text = (title + " " + content).lower()
        for kw, name in COMPANY_KEYWORDS.items():
            if kw in text:
                return name
        return "Unknown"

    def _tag_type(title: str, content: str, existing: str) -> str:
        if existing and existing.lower() != "unknown":
            return existing
        text = (title + " " + content).lower()
        for kw, etype in EVENT_KEYWORDS.items():
            if kw in text:
                return etype
        return "general"

    signals = signals.select(
        timestamp=pw.this.timestamp,
        source=pw.this.source,
        title=pw.this.title,
        content=pw.this.content,
        url=pw.this.url,
        event_id=pw.apply(_compute_id, pw.this.title, pw.this.content, pw.this.url),
        company=pw.apply(_tag_company, pw.this.title, pw.this.content, pw.this.company),
        event_type=pw.apply(_tag_type, pw.this.title, pw.this.content, pw.this.event_type),
    )

    # Shard filter: keep only events where hash % shard_count == shard_id
    # Pathway UDF for sharding
    def _is_my_shard(event_id: str) -> bool:
        return _shard_for(event_id, shard_count) == shard_id

    if shard_count > 1:
        signals = signals.filter(pw.apply(_is_my_shard, pw.this.event_id) == True)  # noqa: E712

    # Dedup by event_id (per shard)
    signals = signals.groupby(pw.this.event_id).reduce(
        timestamp=pw.reducers.max(pw.this.timestamp),
        source=pw.reducers.max(pw.this.source),
        title=pw.reducers.max(pw.this.title),
        content=pw.reducers.max(pw.this.content),
        url=pw.reducers.max(pw.this.url),
        company=pw.reducers.max(pw.this.company),
        event_type=pw.reducers.max(pw.this.event_type),
    )

    pw.io.jsonl.write(signals, str(OUTPUT_FILE))
    pw.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sharded Pathway pipeline")
    parser.add_argument("--shard", type=int, default=int(os.getenv("SHARD_ID", "0")))
    parser.add_argument("--shards", type=int, default=int(os.getenv("SHARD_COUNT", "1")))
    args = parser.parse_args()
    run_sharded(shard_id=args.shard, shard_count=args.shards)
