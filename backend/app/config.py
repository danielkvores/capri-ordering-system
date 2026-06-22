from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./restaurant_orders.db"
    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    llm_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openrouter_site_url: str = "http://localhost:5173"
    openrouter_app_name: str = Field(default="Restaurant Ordering Prototype")

    restaurant_timezone: str = "Europe/Budapest"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
