from __future__ import annotations

import logging
import os

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def _telegram_bot_token() -> str:
	"""Resolve Telegram token for the FastAPI backend notification helper.

	Note: The primary Telegram bot for Ferum runs from the Frappe bench Procfile
	(`apps/ferum_custom/telegram_bot`). This module is intentionally minimal and must not
	import aiogram (heavy import and unnecessary for simple notifications).
	"""
	return (
		(settings.TELEGRAM_BOT_TOKEN or "").strip()
		or (os.getenv("FERUM_TELEGRAM_BOT_TOKEN") or "").strip()
		or (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
	)


async def send_telegram_notification(chat_id: int, text: str) -> None:
	token = _telegram_bot_token()
	if not token:
		logger.warning("Telegram bot token is not configured; skipping notification.")
		return

	url = f"https://api.telegram.org/bot{token}/sendMessage"
	try:
		async with httpx.AsyncClient(timeout=15.0) as client:
			resp = await client.post(url, json={"chat_id": int(chat_id), "text": str(text)})
			resp.raise_for_status()
	except Exception as exc:
		logger.error("Failed to send Telegram notification to %s: %s", chat_id, exc)
