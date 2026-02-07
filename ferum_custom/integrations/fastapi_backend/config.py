from __future__ import annotations

from ferum_custom.config.dotenv import load_dotenv_once
from ferum_custom.config.settings import get_settings

load_dotenv_once()

_conf = get_settings()


class Settings:
	# Backward-compatible default (insecure; flagged by health/audit).
	SECRET_KEY: str = _conf.get("FERUM_JWT_SECRET", "SECRET_KEY") or "super-secret-key"
	ALGORITHM: str = "HS256"
	ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
	ERP_API_URL: str = _conf.get("FERUM_FRAPPE_BASE_URL", "ERP_API_URL") or "http://localhost:8000"
	ERP_API_KEY: str | None = _conf.get("FERUM_FRAPPE_API_KEY", "ERP_API_KEY")
	ERP_API_SECRET: str | None = _conf.get("FERUM_FRAPPE_API_SECRET", "ERP_API_SECRET")
	TELEGRAM_BOT_TOKEN: str | None = _conf.get("FERUM_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
	SENTRY_DSN: str | None = _conf.get("SENTRY_DSN")
	REDIS_URL: str = _conf.get("REDIS_URL") or "redis://localhost:6379/0"


settings = Settings()
