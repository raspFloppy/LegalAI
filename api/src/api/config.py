from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All fields can be overridden via a `.env` file or real environment
    variables.  Defaults are intentionally fake so the app starts for
    local development without a `.env` file, but will not work against
    live external APIs until real keys are supplied.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = "fake-secret-key-please-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    database_url: str = "sqlite+aiosqlite:///./legalai.db"

    telegram_bot_token: str = "fake-telegram-bot-token"
    telegram_webhook_secret: str = "fake-webhook-secret-token"

    gemini_api_key: str = "fake-gemini-api-key"
    gemini_model: str = "gemini-1.5-pro"

    upload_dir: str = "./uploads"
    api_base_url: str = "http://localhost:8000"

    seed_email: str = "lawyer@legalai.com"
    seed_password: str = "legalai2024"
    seed_name: str = "John Smith"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()


settings = get_settings()
