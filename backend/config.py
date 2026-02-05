import os
from pathlib import Path

from ferum_custom.config.dotenv import load_dotenv_once
from ferum_custom.config.settings import get_settings

_dotenv_path = os.getenv("DOTENV_PATH") or os.getenv("FERUM_DOTENV_PATH") or str(Path.cwd() / ".env")
os.environ.setdefault("DOTENV_PATH", _dotenv_path)
load_dotenv_once()

_conf = get_settings()


class Settings:
	# Backward-compatible default (insecure; flagged by health/audit).
	SECRET_KEY: str = _conf.get("SECRET_KEY") or "super-secret-key"
	ALGORITHM: str = "HS256"
	ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
	ERP_API_URL: str = _conf.get("ERP_API_URL", "FERUM_FRAPPE_BASE_URL") or "http://localhost:8000"
	ERP_API_KEY: str | None = _conf.get("ERP_API_KEY", "FERUM_FRAPPE_API_KEY")
	ERP_API_SECRET: str | None = _conf.get("ERP_API_SECRET", "FERUM_FRAPPE_API_SECRET")
	TELEGRAM_BOT_TOKEN: str | None = _conf.get("TELEGRAM_BOT_TOKEN", "FERUM_TELEGRAM_BOT_TOKEN")
	SENTRY_DSN: str | None = _conf.get("SENTRY_DSN")
	REDIS_URL: str = _conf.get("REDIS_URL") or "redis://localhost:6379/0"


settings = Settings()
