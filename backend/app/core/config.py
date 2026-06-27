"""
Application configuration loaded from environment variables.
All settings are validated at startup via Pydantic.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "MarketLens"
    environment: str = "development"
    debug: bool = False

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Database (direct Postgres connection for SQLAlchemy)
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/dbname

    # AI
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # LLM model selection
    analysis_model: str = "gpt-4o"
    judge_model: str = "gpt-4o-mini"

    # Crawler
    crawler_timeout_seconds: int = 30
    max_urls_per_run: int = 10

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
