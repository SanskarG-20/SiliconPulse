import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    app_name: str = "SiliconPulse API"
    clerk_issuer: str = os.getenv("CLERK_ISSUER", "")
    clerk_audience: str = os.getenv("CLERK_AUDIENCE", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    gemini_fallback_models: list[str] = ["gemini-1.5-pro", "gemini-1.0-pro"]
    data_stream_path: str = os.getenv("DATA_STREAM_PATH", "data/stream.jsonl")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    
    # Deduplication & Freshness Settings
    freshness_hours: int = int(os.getenv("FRESHNESS_HOURS", "12"))
    max_events_to_scan: int = int(os.getenv("MAX_EVENTS_TO_SCAN", "500"))
    dedup_enabled: bool = os.getenv("DEDUP_ENABLED", "true").lower() == "true"
    checkpoint_enabled: bool = os.getenv("CHECKPOINT_ENABLED", "true").lower() == "true"
    db_path: str = os.getenv("DB_PATH", "data/siliconpulse.db")
    
    # Pathway Settings
    use_pathway: bool = os.getenv("USE_PATHWAY", "True").lower() == "true"
    pathway_output_path: str = os.getenv("PATHWAY_OUTPUT_PATH", "data/pathway_out.jsonl")
    
    # GDELT Settings (free API)
    gdelt_enabled: bool = os.getenv("GDELT_ENABLED", "True").lower() == "true"
    
    # HackerNews Settings (free Algolia API)
    hackernews_enabled: bool = os.getenv("HACKERNEWS_ENABLED", "True").lower() == "true"

    # External news providers (free APIs)
    newsdata_api_key: str = os.getenv("NEWSDATA_API_KEY", "")
    newsapi_api_key: str = os.getenv("NEWSAPI_API_KEY", "")
    gnews_api_key: str = os.getenv("GNEWS_API_KEY", "")
    mediastack_api_key: str = os.getenv("MEDIASTACK_API_KEY", "")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

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
