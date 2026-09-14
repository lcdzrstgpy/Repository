from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "代发仓 ERP 中枢"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/warehouse_erp"
    jwt_secret: str = Field(default="change-this-in-production-at-least-32-bytes", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    wms_api_token: str = Field(default="change-this-wms-token", min_length=16)
    webhook_secret: str = Field(default="change-this-webhook-secret", min_length=16)
    webhook_tolerance_seconds: int = 300
    sentry_base_url: str = "http://localhost:5000/api/v1"
    sentry_token: str = "change-this-sentry-token"
    sentry_timeout_seconds: float = 10.0
    bootstrap_username: str | None = None
    bootstrap_password: str | None = None
    seed_default_categories: bool = True
    timeout_scan_interval_seconds: int = Field(default=300, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
