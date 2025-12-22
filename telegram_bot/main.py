from __future__ import annotations

import asyncio
import logging
import os

import httpx
from aiogram import Bot, Dispatcher

from .telegram_bot.frappe import FrappeAPI
from .telegram_bot.handlers.commands import build_router, default_commands
from .telegram_bot.settings import Settings, load_settings


logger = logging.getLogger("ferum.telegram.bot")


def _frappe_api(settings: Settings, client: httpx.AsyncClient) -> FrappeAPI | None:
	if not settings.frappe_base_url:
		return None
	return FrappeAPI(
		settings.frappe_base_url,
		api_key=settings.frappe_api_key,
		api_secret=settings.frappe_api_secret,
		client=client,
	)


async def _run_webhook(dp: Dispatcher, bot: Bot, settings: Settings) -> None:
	from aiohttp import web
	from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

	assert settings.webhook_url, "webhook_url required"

	app = web.Application()
	app.router.add_get("/tg-bot/health", lambda request: web.json_response({"status": "ok"}))
	SimpleRequestHandler(
		dispatcher=dp, bot=bot, secret_token=settings.webhook_secret
	).register(app, path=settings.webhook_path)
	setup_application(app, dp, bot=bot)

	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)
	await site.start()

	webhook_full_url = f"{settings.webhook_url}{settings.webhook_path}"
	logger.info(
		"Starting webhook mode on %s:%s%s",
		settings.webhook_host,
		settings.webhook_port,
		settings.webhook_path,
	)
	await bot.set_webhook(
		webhook_full_url,
		secret_token=settings.webhook_secret,
		drop_pending_updates=True,
	)

	try:
		while True:
			await asyncio.sleep(3600)
	finally:
		await bot.delete_webhook(drop_pending_updates=False)
		await runner.cleanup()


async def _run_once() -> None:
	settings = load_settings()

	bot = Bot(token=settings.telegram_bot_token)
	dp = Dispatcher()
	async with httpx.AsyncClient() as http_client:
		api = _frappe_api(settings, http_client)
		dp.include_router(build_router(settings, api))

		try:
			await bot.set_my_commands(default_commands())
		except Exception:
			logger.exception("Failed to set bot commands")

		try:
			me = await bot.get_me()
			logger.info("Bot started as @%s (id=%s), mode=%s", me.username, me.id, settings.mode)
		except Exception:
			logger.exception("Failed to fetch bot identity")

		if settings.mode == "webhook":
			await _run_webhook(dp, bot, settings)
			return

		# Default to polling.
		await bot.delete_webhook(drop_pending_updates=True)
		await dp.start_polling(bot)


if __name__ == "__main__":
	def _parse_backoff(raw: str) -> float:
		try:
			value = float(raw)
		except Exception:
			return 5.0
		return max(1.0, value)

	async def _run_forever() -> None:
		backoff = _parse_backoff(os.getenv("FERUM_TELEGRAM_RESTART_BACKOFF_SECONDS") or "5")
		while True:
			try:
				await _run_once()
				# If polling/webhook stops gracefully, do not spin/restart.
				logger.info("Telegram bot stopped.")
				return
			except Exception:
				logger.exception("Telegram bot crashed; retrying in %ss", backoff)
				await asyncio.sleep(backoff)

	logging.basicConfig(level=logging.INFO)
	asyncio.run(_run_forever())
