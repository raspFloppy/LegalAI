from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Walk up from dashboard/src/dashboard/config.py  →  …  →  legalai/
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Dashboard application settings.

    Attributes:
        api_url: Base URL of the LegalAI API service.
        nicegui_secret_key: Secret key used by NiceGUI to sign session cookies.
        host: Host interface to bind the NiceGUI server.
        port: Port to listen on.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_url: str = "http://localhost:8000"
    nicegui_secret_key: str = "change-me-nicegui-secret"
    host: str = "0.0.0.0"
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the dashboard settings."""
    return Settings()


settings = get_settings()
