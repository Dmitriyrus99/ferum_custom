from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ferum_custom.config.dotenv import load_dotenv_once
from ferum_custom.config.settings import get_settings


@dataclass(frozen=True)
class Settings:
	telegram_bot_token: str
	mode: str

	frappe_base_url: str | None
	frappe_api_key: str | None
	frappe_api_secret: str | None
	default_company: str | None

	webhook_url: str | None
	webhook_path: str
	webhook_secret: str | None
	webhook_host: str
	webhook_port: int

	allowed_chat_ids: set[int] | None
	require_registration: bool


def _find_dotenv_path() -> str:
	# Explicit override first (used by systemd/docker).
	explicit = os.getenv("DOTENV_PATH") or os.getenv("FERUM_DOTENV_PATH")
	if explicit:
		return explicit

	# Local `.env` in current working directory (common for local runs).
	cwd_env = Path.cwd() / ".env"
	if cwd_env.exists():
		return str(cwd_env)

	# Bench root `.env` (common when the bot is run from `apps/ferum_custom/...`).
	# settings.py -> telegram_bot -> telegram_bot -> telegram_bot -> apps/ferum_custom -> apps -> bench root
	for parent in Path(__file__).resolve().parents[:8]:
		candidate = parent / ".env"
		if candidate.exists():
			return str(candidate)

	# Fallback: keep previous behavior.
	return str(cwd_env)


def load_settings() -> Settings:
	# Prefer explicit dotenv path resolution used by the bot, but share the common loader.
	dotenv_path = _find_dotenv_path()
	os.environ.setdefault("DOTENV_PATH", dotenv_path)
	load_dotenv_once()
	conf = get_settings()

	telegram_bot_token = conf.get("FERUM_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN") or ""
	mode = (conf.get("MODE", "FERUM_TELEGRAM_MODE") or "polling").strip().lower()

	frappe_base_url = (conf.get("FERUM_FRAPPE_BASE_URL", "ERP_API_URL") or "").strip() or None
	frappe_api_key = (conf.get("FERUM_FRAPPE_API_KEY", "ERP_API_KEY") or "").strip() or None
	frappe_api_secret = (conf.get("FERUM_FRAPPE_API_SECRET", "ERP_API_SECRET") or "").strip() or None
	default_company = (conf.get("FERUM_DEFAULT_COMPANY", "DEFAULT_COMPANY") or "").strip() or None

	webhook_url = (conf.get("FERUM_TELEGRAM_WEBHOOK_URL", "TELEGRAM_WEBHOOK_URL") or "").strip() or None
	webhook_path = (
		conf.get("FERUM_TELEGRAM_WEBHOOK_PATH", "TELEGRAM_WEBHOOK_PATH") or "/tg-bot/webhook"
	).strip()
	if not webhook_path.startswith("/"):
		webhook_path = "/" + webhook_path
	webhook_secret = (
		conf.get("FERUM_TELEGRAM_WEBHOOK_SECRET", "TELEGRAM_WEBHOOK_SECRET") or ""
	).strip() or None
	webhook_host = (conf.get("FERUM_TELEGRAM_WEBHOOK_HOST") or "0.0.0.0").strip() or "0.0.0.0"
	webhook_port = conf.get_int("FERUM_TELEGRAM_WEBHOOK_PORT", "TELEGRAM_WEBHOOK_PORT", default=8080) or 8080

	allowed_chat_ids = conf.get_int_set("FERUM_TELEGRAM_ALLOWED_CHAT_IDS")
	require_registration = conf.get_bool("FERUM_TELEGRAM_REQUIRE_REGISTRATION", default=False)

	missing = []
	if not telegram_bot_token:
		missing.append("FERUM_TELEGRAM_BOT_TOKEN")
	if mode == "webhook" and not webhook_url:
		missing.append("FERUM_TELEGRAM_WEBHOOK_URL")
	if missing:
		raise RuntimeError(f"Telegram bot is not configured; missing: {', '.join(missing)}")

	return Settings(
		telegram_bot_token=telegram_bot_token,
		mode=mode,
		frappe_base_url=frappe_base_url.rstrip("/") if frappe_base_url else None,
		frappe_api_key=frappe_api_key,
		frappe_api_secret=frappe_api_secret,
		default_company=default_company,
		webhook_url=webhook_url.rstrip("/") if webhook_url else None,
		webhook_path=webhook_path,
		webhook_secret=webhook_secret,
		webhook_host=webhook_host,
		webhook_port=webhook_port,
		allowed_chat_ids=allowed_chat_ids,
		require_registration=require_registration,
	)
