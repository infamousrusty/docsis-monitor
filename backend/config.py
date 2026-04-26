from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Router
    ROUTER_IP: str = "192.168.100.1"
    ROUTER_SCHEME: str = "http"
    POLL_INTERVAL: int = 30
    REQUEST_TIMEOUT: int = 10
    REQUEST_RETRIES: int = 3
    ROUTER_USER: str | None = None
    ROUTER_PASS: str | None = None

    # Thresholds
    SNR_WARN_DB: float = 33.0
    SNR_CRIT_DB: float = 30.0
    DS_POWER_MIN: float = -7.0
    DS_POWER_MAX: float = 7.0
    US_POWER_MIN: float = 38.0
    US_POWER_MAX: float = 48.5
    UNCORRECTABLE_WARN: int = 100
    UNCORRECTABLE_CRIT: int = 500
    T3_T4_CRIT_COUNT: int = 1

    # Alerting
    WEBHOOK_URLS: str = ""
    ALERT_DEBOUNCE_SECONDS: int = 300
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASS: str | None = None
    SMTP_TO: str | None = None
    SMTP_FROM: str = "docsis-monitor@localhost"

    # Storage
    DB_PATH: str = "/data/docsis.db"
    DATA_RETENTION_DAYS: int = 90

    # App
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    BASIC_AUTH_USER: str | None = None
    BASIC_AUTH_PASS: str | None = None

    @property
    def webhook_list(self) -> list[str]:
        if not self.WEBHOOK_URLS:
            return []
        return [u.strip() for u in self.WEBHOOK_URLS.split(",") if u.strip()]

    @property
    def router_base_url(self) -> str:
        return f"{self.ROUTER_SCHEME}://{self.ROUTER_IP}"

    model_config = {"env_file": ".env"}


settings = Settings()
