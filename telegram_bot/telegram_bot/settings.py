from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


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
	# Load bench `.env` explicitly.
	dotenv_path = _find_dotenv_path()
	load_dotenv(dotenv_path=dotenv_path, override=False)

	telegram_bot_token = os.getenv("FERUM_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
	mode = (os.getenv("MODE") or os.getenv("FERUM_TELEGRAM_MODE") or "polling").strip().lower()

	frappe_base_url = (os.getenv("FERUM_FRAPPE_BASE_URL") or os.getenv("ERP_API_URL") or "").strip() or None
	frappe_api_key = (os.getenv("FERUM_FRAPPE_API_KEY") or os.getenv("ERP_API_KEY") or "").strip() or None
	frappe_api_secret = (
		os.getenv("FERUM_FRAPPE_API_SECRET") or os.getenv("ERP_API_SECRET") or ""
	).strip() or None
	default_company = (
		os.getenv("FERUM_DEFAULT_COMPANY") or os.getenv("DEFAULT_COMPANY") or ""
	).strip() or None

	webhook_url = (
		os.getenv("FERUM_TELEGRAM_WEBHOOK_URL") or os.getenv("TELEGRAM_WEBHOOK_URL") or ""
	).strip() or None
	webhook_path = (
		os.getenv("FERUM_TELEGRAM_WEBHOOK_PATH") or os.getenv("TELEGRAM_WEBHOOK_PATH") or "/tg-bot/webhook"
	).strip()
	if not webhook_path.startswith("/"):
		webhook_path = "/" + webhook_path
	webhook_secret = (
		os.getenv("FERUM_TELEGRAM_WEBHOOK_SECRET") or os.getenv("TELEGRAM_WEBHOOK_SECRET") or ""
	).strip() or None
	webhook_host = (os.getenv("FERUM_TELEGRAM_WEBHOOK_HOST") or "0.0.0.0").strip() or "0.0.0.0"
	webhook_port_raw = (os.getenv("FERUM_TELEGRAM_WEBHOOK_PORT") or "8080").strip()
	try:
		webhook_port = int(webhook_port_raw)
	except ValueError:
		webhook_port = 8080

	allowed_chat_ids_raw = (os.getenv("FERUM_TELEGRAM_ALLOWED_CHAT_IDS") or "").strip()
	allowed_chat_ids: set[int] | None = None
	if allowed_chat_ids_raw:
		allowed_chat_ids = set()
		for part in allowed_chat_ids_raw.split(","):
			part = part.strip()
			if not part:
				continue
			try:
				allowed_chat_ids.add(int(part))
			except ValueError:
				continue

	require_registration_raw = (os.getenv("FERUM_TELEGRAM_REQUIRE_REGISTRATION") or "").strip().lower()
	require_registration = require_registration_raw in {"1", "true", "yes", "on"}

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
