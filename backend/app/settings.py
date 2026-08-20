import os
import platform
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    app_name: str = "SiliconPulse API"
    clerk_issuer: str = ""
    clerk_audience: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_fallback_models: list[str] = ["gemini-1.5-pro", "gemini-1.0-pro"]
    data_stream_path: str = "data/stream.jsonl"
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Deduplication & Freshness Settings
    freshness_hours: int = 12
    max_events_to_scan: int = 500
    dedup_enabled: bool = True
    checkpoint_enabled: bool = True
    db_path: str = "data/siliconpulse.db"
    
    # Pathway Settings - Default False on Windows since Pathway doesn't run natively
    use_pathway: bool = platform.system() != "Windows"
    pathway_output_path: str = "data/pathway_out.jsonl"
    
    # GDELT Settings (free API)
    gdelt_enabled: bool = True
    
    # HackerNews Settings (free Algolia API)
    hackernews_enabled: bool = True

    # External news providers (free APIs)
    newsapi_api_key: str = ""
    
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

    @property
    def resolved_pathway_path(self) -> Path:
        """Resolve pathway output path to absolute path"""
        path = Path(self.pathway_output_path)
        if path.is_absolute():
            return path
        base_dir = Path(__file__).resolve().parent.parent
        return base_dir / path

settings = Settings()
