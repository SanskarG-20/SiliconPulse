from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    app_name: str = "SiliconPulse API"
    app_env: str = "development"
    clerk_issuer: str = ""
    clerk_audience: str = ""
    privileged_inject_role: str = "admin"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""  # optional, enables per-user RLS via anon + JWT
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_fallback_models: list[str] = ["gemini-1.5-pro", "gemini-1.0-pro"]
    data_stream_path: str = "data/stream.jsonl"
    local_cache_enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Deduplication & Freshness Settings
    freshness_hours: int = 12
    max_events_to_scan: int = 500
    dedup_enabled: bool = True
    checkpoint_enabled: bool = True
    db_path: str = "data/siliconpulse.db"
    ingestion_lookback_hours: int = 72

    # GDELT Settings (free API)
    gdelt_enabled: bool = True

    # HackerNews Settings (free Algolia API)
    hackernews_enabled: bool = True

    # External news providers (free APIs)
    newsapi_api_key: str = ""
    youtube_api_key: str = ""  # YouTube Data API v3 key for Intelligence Videos
    redis_url: str = ""  # optional: redis://... for distributed rate limiting

    # Shared LLM usage controls (daily UTC reset).
    llm_daily_token_budget: int = 500_000
    llm_user_daily_calls: int = 50
    llm_max_output_tokens: int = 2048
    gemini_input_cost_usd_per_million: Optional[float] = None
    gemini_output_cost_usd_per_million: Optional[float] = None
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "siliconpulse-api"
    ingestion_lag_alert_seconds: int = 3600

    # Distributed workers (1M+ events/day)
    worker_count: int = 4
    worker_batch_size: int = 50
    use_distributed_workers: bool = False

    # Scheduled digest delivery (Phase 2.3)
    resend_api_key: str = ""  # Resend API key for morning briefing emails
    resend_from_email: str = "SiliconPulse <onboarding@resend.dev>"

    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        case_sensitive = False,
        extra = "ignore"
    )

    @property
    def resolved_data_path(self) -> Path:
        """Resolve data stream path to absolute path"""
        path = Path(self.data_stream_path)
        if path.is_absolute():
            return path
        # Resolve relative to backend root
        base_dir = Path(__file__).resolve().parent.parent
        return base_dir / path

settings = Settings()
