from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

_PLACEHOLDER_KEY = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    app_name: str = "GEOCopilot"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/geocopilot"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/geocopilot"

    @model_validator(mode="after")
    def fix_database_urls(self) -> "Settings":
        # Railway provides DATABASE_URL as postgresql:// but async engine needs postgresql+asyncpg://
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # JWT
    secret_key: str = _PLACEHOLDER_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    @model_validator(mode="after")
    def enforce_secret_key(self) -> "Settings":
        if self.environment != "development" and self.secret_key == _PLACEHOLDER_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a secure value via env var in non-development environments"
            )
        return self

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # Email (SendGrid)
    sendgrid_api_key: str = ""
    email_from: str = "noreply@geocopilot.ai"
    email_from_name: str = "GEOCopilot"

    # Frontend
    frontend_url: str = "http://localhost:5173"

    # SERP API (chosen: SerpAPI — better AI Overviews coverage)
    serp_api_provider: str = "serpapi"
    serp_api_key: str = ""
    valueserp_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
