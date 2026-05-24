from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Dashboard application settings.

    Attributes:
        api_url: Base URL of the LegalAI API service.
        nicegui_secret_key: Secret key used by NiceGUI to sign session cookies.
        host: Host interface to bind the NiceGUI server.
        port: Port to listen on.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
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
