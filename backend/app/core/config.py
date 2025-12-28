"""
Application configuration settings.

All configuration is loaded from environment variables with sensible defaults.
"""
import json
from typing import Any
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "Dualcaster Deals"
    api_debug: bool = True
    secret_key: str = "dev-secret-key-change-in-production"  # SECURITY: Must be overridden in production via env var
    
    # JWT Settings
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours

    # OAuth settings
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    OAUTH_ENABLED: bool = False

    # Domain settings for production
    domain: str = "localhost"
    frontend_url: str = "http://localhost:3000"
    
    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]
    
    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "mtg_user"
    postgres_password: str = "mtg_password"
    postgres_db: str = "mtg_market_intel"
    database_url: str | None = None
    
    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    
    # LLM Configuration
    llm_provider: str = "openai"  # openai, anthropic, local
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-haiku-20240307"
    local_llm_url: str = "http://localhost:11434"
    local_llm_model: str = "llama2"
    
    # Scryfall API
    # Rate limit: 50-100ms between requests (10 requests/second average)
    # Using 75ms as a safe middle ground
    scryfall_base_url: str = "https://api.scryfall.com"
    scryfall_rate_limit_ms: int = 75
    
    # Marketplace API Keys
    tcgplayer_api_key: str = ""
    tcgplayer_api_secret: str = ""
    cardmarket_app_token: str = ""
    cardmarket_app_secret: str = ""
    cardmarket_access_token: str = ""
    cardmarket_access_secret: str = ""
    cardtrader_api_token: str = ""  # CardTrader API JWT token - set via CARDTRADER_API_TOKEN env var
    cardtrader_secret_key: str = ""
    manapool_api_token: str = ""  # Manapool API token - set via MANAPOOL_API_TOKEN env var

    # Tournament Data API Keys
    topdeck_api_key: str = ""  # TopDeck.gg API key - set via TOPDECK_API_KEY env var
    
    # Scraping Configuration
    scraper_user_agent: str = "MTGMarketIntel/1.0"
    scraper_rate_limit_seconds: float = 1.0
    scraper_max_retries: int = 3
    scraper_backoff_factor: float = 2.0
    
    # Scheduled Tasks
    # Note: Price collection now runs every 5 minutes (configured in celery_app.py)
    # Data older than 24 hours is considered stale
    analytics_interval_hours: int = 1
    recommendations_interval_hours: int = 6
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v
    
    @property
    def database_url_computed(self) -> str:
        """Compute database URL from components if not explicitly set."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    
    # Security check: warn if using default secret key in production
    if not settings.api_debug and settings.secret_key == "dev-secret-key-change-in-production":
        import warnings
        warnings.warn(
            "SECURITY WARNING: Using default secret_key in production! "
            "Set SECRET_KEY environment variable to a secure random value.",
            UserWarning
        )
    
    return settings


settings = get_settings()

