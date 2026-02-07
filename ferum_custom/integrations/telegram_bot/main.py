from __future__ import annotations

import asyncio
import logging
import os
import socket

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

from .frappe import FrappeAPI
from .handlers.commands import build_router, default_commands
from .settings import Settings, load_settings

logger = logging.getLogger("ferum.telegram.bot")
_LOCK_FD: int | None = None


def _parse_backoff(raw: str) -> float:
	try:
		value = float(raw)
	except Exception:
		return 5.0
	return max(1.0, value)


def _frappe_api(settings: Settings, client: httpx.AsyncClient) -> FrappeAPI | None:
	if not settings.frappe_base_url:
		return None
	return FrappeAPI(
		settings.frappe_base_url,
		api_key=settings.frappe_api_key,
		api_secret=settings.frappe_api_secret,
		client=client,
	)


def _dns_preflight() -> None:
	"""Best-effort DNS check for Telegram API.

	If DNS is broken in container/VM (common when `/etc/resolv.conf` points to 127.0.0.53 without systemd-resolved),
	the bot can receive webhooks but won't be able to send replies.
	"""
	try:
		socket.getaddrinfo("api.telegram.org", 443)
	except Exception as exc:
		logger.error(
			"DNS resolution failed for api.telegram.org: %s. "
			"Check /etc/resolv.conf and container DNS configuration.",
			exc,
		)


def _acquire_single_instance_lock() -> None:
	"""Prevent multiple bot instances from binding the same webhook port.

	This commonly happens when `bench start` is run in multiple shells.
	We use a simple filesystem lock so a second instance blocks until the first exits.
	"""
	global _LOCK_FD
	try:
		import fcntl
		from pathlib import Path
	except Exception:  # pragma: no cover
		return

	lock_path = (os.getenv("FERUM_TELEGRAM_LOCK_FILE") or "").strip()
	if not lock_path:
		try:
			from .settings import _find_dotenv_path

			lock_path = str(Path(_find_dotenv_path()).resolve().parent / ".ferum_telegram_bot.lock")
		except Exception:
			lock_path = "/tmp/ferum_telegram_bot.lock"

	fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o664)
	try:
		fcntl.flock(fd, fcntl.LOCK_EX)
		try:
			os.ftruncate(fd, 0)
			os.write(fd, str(os.getpid()).encode())
		except Exception:
			pass
	except Exception:
		os.close(fd)
		raise

	_LOCK_FD = fd


async def _run_webhook(dp: Dispatcher, bot: Bot, settings: Settings) -> None:
	from aiogram.exceptions import TelegramNetworkError
	from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
	from aiohttp import web

	assert settings.webhook_url, "webhook_url required"

	app = web.Application()
	app.router.add_get("/health", lambda request: web.json_response({"status": "ok"}))
	app.router.add_get("/tg-bot/health", lambda request: web.json_response({"status": "ok"}))
	SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret).register(
		app, path=settings.webhook_path
	)
	setup_application(app, dp, bot=bot)

	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)
	try:
		await site.start()
	except OSError as exc:
		if getattr(exc, "errno", None) == 98:  # address already in use
			logger.error(
				"Webhook port %s is already in use. Check for duplicate bot processes and bench restarts.",
				settings.webhook_port,
			)
		raise

	webhook_full_url = f"{settings.webhook_url}{settings.webhook_path}"
	logger.info(
		"Starting webhook mode on %s:%s%s",
		settings.webhook_host,
		settings.webhook_port,
		settings.webhook_path,
	)

	try:
		# If Telegram API is temporarily unavailable (DNS/network), don't crash:
		# webhook might already be configured, and we still want to process incoming updates.
		try:
			await bot.set_webhook(
				webhook_full_url,
				secret_token=settings.webhook_secret,
				drop_pending_updates=True,
			)
		except TelegramNetworkError:
			logger.exception("Failed to set webhook (network error). Keeping server running anyway.")

		while True:
			await asyncio.sleep(3600)
	finally:
		try:
			await bot.delete_webhook(drop_pending_updates=False)
		except Exception:
			logger.exception("Failed to delete webhook during shutdown")
		await runner.cleanup()


async def _run_once() -> None:
	settings = load_settings()
	_dns_preflight()

	# Force IPv4 for Telegram API calls to avoid intermittent IPv6/DNS issues seen in production logs.
	telegram_session = AiohttpSession(timeout=20.0)
	telegram_session._connector_init["family"] = socket.AF_INET
	bot = Bot(token=settings.telegram_bot_token, session=telegram_session)
	dp = Dispatcher(storage=MemoryStorage())
	try:
		async with httpx.AsyncClient() as http_client:
			api = _frappe_api(settings, http_client)
			dp.include_router(build_router(settings, api))

			try:
				await bot.set_my_commands(default_commands())
			except Exception as e:
				# Avoid noisy crash-loops on frequent restarts.
				from aiogram.exceptions import TelegramRetryAfter

				if isinstance(e, TelegramRetryAfter):
					logger.warning(
						"Telegram rate limit on SetMyCommands; retry after %ss. Skipping for now.",
						getattr(e, "retry_after", None),
					)
				else:
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
	finally:
		# Avoid aiohttp warnings/leaks on crashes/restarts.
		try:
			await bot.session.close()
		except Exception:
			logger.exception("Failed to close bot session")


async def run_forever() -> None:
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


def main() -> None:
	logging.basicConfig(level=logging.INFO)
	_acquire_single_instance_lock()
	asyncio.run(run_forever())


if __name__ == "__main__":
	main()
