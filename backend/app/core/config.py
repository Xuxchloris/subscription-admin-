from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Hermes Admin"
    database_url: str = "sqlite:///./hermes_admin.db"
    jwt_secret: str = "change-this-secret-before-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 720
    hermes_binary: str = "hermes"
    hermes_home: Path = Path.home() / ".hermes"

    model_config = SettingsConfigDict(env_prefix="HERMES_ADMIN_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
