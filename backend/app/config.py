"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://riskdash:riskdash@localhost:5432/riskdash"
    database_url_sync: str = "postgresql://riskdash:riskdash@localhost:5432/riskdash"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Data
    tickers: str = "^GSPC,GLE.PA,SIE.DE"
    fx_pair: str = "EURUSD=X"
    base_currency: str = "EUR"
    backfill_years: int = 5

    # Scheduling
    ingestion_cron_hour: int = 22
    ingestion_cron_minute: int = 15

    @property
    def ticker_list(self) -> list[str]:
        return [t.strip() for t in self.tickers.split(",")]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
