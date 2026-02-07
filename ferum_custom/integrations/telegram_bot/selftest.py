from __future__ import annotations

import asyncio
import socket

import httpx
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from .frappe import FrappeAPI
from .settings import Settings, load_settings


def _frappe_api(settings: Settings, client: httpx.AsyncClient) -> FrappeAPI | None:
	if not settings.frappe_base_url:
		return None
	return FrappeAPI(
		settings.frappe_base_url,
		api_key=settings.frappe_api_key,
		api_secret=settings.frappe_api_secret,
		client=client,
	)


async def _run() -> int:
	settings = load_settings()

	print(f"mode={settings.mode}")
	print(f"frappe_base_url_set={bool(settings.frappe_base_url)}")
	print(f"frappe_api_token_set={bool(settings.frappe_api_key and settings.frappe_api_secret)}")

	telegram_session = AiohttpSession(timeout=20.0)
	telegram_session._connector_init["family"] = socket.AF_INET
	bot = Bot(token=settings.telegram_bot_token, session=telegram_session)

	try:
		me = await bot.get_me()
		print(f"telegram_get_me=ok username=@{me.username} id={me.id}")

		if settings.mode == "webhook":
			info = await bot.get_webhook_info()
			print(f"webhook_url={info.url or '-'}")
			if info.last_error_message:
				print(f"webhook_last_error={info.last_error_message}")
			print(f"pending_update_count={info.pending_update_count}")

		async with httpx.AsyncClient() as http_client:
			api = _frappe_api(settings, http_client)
			if api:
				try:
					resp = await api.call_message("frappe.ping", {}, http_method="GET", timeout=15.0)
					print(f"frappe_ping={resp!r}")
				except Exception as e:
					print(f"frappe_ping=error {type(e).__name__}: {e}")
			else:
				print("frappe_ping=skipped (no ERP API config)")

		return 0
	finally:
		try:
			await bot.session.close()
		except Exception:
			pass


def main() -> int:
	return int(asyncio.run(_run()))


if __name__ == "__main__":
	raise SystemExit(main())
