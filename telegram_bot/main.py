from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
import requests


logger = logging.getLogger("ferum.telegram.bot")


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


def _load_settings() -> Settings:
	# Load bench `.env` explicitly.
	dotenv_path = os.getenv("DOTENV_PATH") or os.getenv("FERUM_DOTENV_PATH") or str(Path.cwd() / ".env")
	load_dotenv(dotenv_path=dotenv_path, override=False)

	telegram_bot_token = os.getenv("FERUM_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
	mode = (os.getenv("MODE") or os.getenv("FERUM_TELEGRAM_MODE") or "polling").strip().lower()

	frappe_base_url = (os.getenv("FERUM_FRAPPE_BASE_URL") or os.getenv("ERP_API_URL") or "").strip() or None
	frappe_api_key = (os.getenv("FERUM_FRAPPE_API_KEY") or os.getenv("ERP_API_KEY") or "").strip() or None
	frappe_api_secret = (os.getenv("FERUM_FRAPPE_API_SECRET") or os.getenv("ERP_API_SECRET") or "").strip() or None
	default_company = (os.getenv("FERUM_DEFAULT_COMPANY") or os.getenv("DEFAULT_COMPANY") or "").strip() or None

	webhook_url = (os.getenv("FERUM_TELEGRAM_WEBHOOK_URL") or os.getenv("TELEGRAM_WEBHOOK_URL") or "").strip() or None
	webhook_path = (os.getenv("FERUM_TELEGRAM_WEBHOOK_PATH") or os.getenv("TELEGRAM_WEBHOOK_PATH") or "/tg-bot/webhook").strip()
	if not webhook_path.startswith("/"):
		webhook_path = "/" + webhook_path
	webhook_secret = (
		(os.getenv("FERUM_TELEGRAM_WEBHOOK_SECRET") or os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()
		or None
	)
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
	)


class FrappeAPI:
	def __init__(self, base_url: str, api_key: str | None, api_secret: str | None) -> None:
		self.base_url = base_url.rstrip("/")
		self.session = requests.Session()
		self.session.headers.update({"Accept": "application/json"})
		if api_key and api_secret:
			self.session.headers.update({"Authorization": f"token {api_key}:{api_secret}"})

	def get_list(
		self,
		doctype: str,
		*,
		fields: list[str] | None = None,
		order_by: str | None = None,
		limit_page_length: int | None = None,
	) -> list[dict]:
		params: dict[str, str] = {}
		if fields is not None:
			params["fields"] = json.dumps(fields)
		if order_by:
			params["order_by"] = order_by
		if limit_page_length is not None:
			params["limit_page_length"] = str(limit_page_length)
		url = f"{self.base_url}/api/resource/{quote(doctype, safe='')}"
		resp = self.session.get(url, params=params, timeout=20)
		resp.raise_for_status()
		payload = resp.json()
		return payload.get("data") or []

	def insert(self, doctype: str, data: dict) -> dict:
		url = f"{self.base_url}/api/resource/{quote(doctype, safe='')}"
		resp = self.session.post(url, json={"data": data}, timeout=20)
		resp.raise_for_status()
		payload = resp.json()
		return payload.get("data") or {}

	def call(self, method: str, params: dict | None = None) -> dict:
		url = f"{self.base_url}/api/method/{method}"
		resp = self.session.get(url, params=params or {}, timeout=20)
		resp.raise_for_status()
		return resp.json()


def _frappe_api(settings: Settings) -> FrappeAPI | None:
	if not settings.frappe_base_url:
		return None
	return FrappeAPI(settings.frappe_base_url, settings.frappe_api_key, settings.frappe_api_secret)


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


async def main() -> None:
	logging.basicConfig(level=logging.INFO)
	settings = _load_settings()

	bot = Bot(token=settings.telegram_bot_token)
	dp = Dispatcher()
	api = _frappe_api(settings)

	try:
		me = await bot.get_me()
		logger.info("Bot started as @%s (id=%s), mode=%s", me.username, me.id, settings.mode)
	except Exception:
		logger.exception("Failed to fetch bot identity")

	def _chat_allowed(message: Message) -> bool:
		if settings.allowed_chat_ids is None:
			return True
		try:
			return int(message.chat.id) in settings.allowed_chat_ids
		except Exception:
			return False

	@dp.message(CommandStart())
	async def start(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer("Ferum bot is online. Use /help for commands.")

	@dp.message(Command("help"))
	async def help_cmd(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer(
			"/chatid — показать chat_id\n"
			"/register [user_email] — зарегистрировать чат/пользователя для уведомлений\n"
			"/me — проверка доступа к ERP API\n"
			"/requests — последние 10 Service Request\n"
			"/new_request <title> — создать Service Request\n"
			"/invoices — последние 10 Invoice\n"
		)

	@dp.message(Command("chatid"))
	async def chatid(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer(
			f"chat_id={message.chat.id}\n"
			f"from=@{message.from_user.username if message.from_user else ''}\n"
		)

	@dp.message(Command("register"))
	async def register(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		user_email = (message.text or "").replace("/register", "", 1).strip() or None
		try:
			payload = {
				"telegram_username": (message.from_user.username if message.from_user else "") or "",
				"chat_id": str(message.chat.id),
				"notes": f"tg_user_id={message.from_user.id if message.from_user else ''}",
			}
			if user_email:
				# Best-effort pre-link (admin can correct later).
				payload["user"] = user_email
			created = api.insert("Telegram User Link", payload)
			await message.answer(f"Registered. Telegram User Link: {created.get('name')}")
		except Exception:
			logger.exception("register failed")
			await message.answer("Registration failed (see logs).")

	@dp.message()
	async def fallback(message: Message) -> None:
		# Respond to any non-command message so users see the bot is alive.
		if not _chat_allowed(message):
			return
		if message.text and message.text.startswith("/"):
			return
		await message.answer("Я на связи. Команды: /help")

	@dp.message(Command("me"))
	async def me(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		try:
			# Simple request to validate credentials.
			api.get_list("User", fields=["name"], limit_page_length=1)
			await message.answer("ERP API: OK")
		except Exception:
			logger.exception("ERP API check failed")
			await message.answer("ERP API: ERROR (see logs)")

	@dp.message(Command("my"))
	async def my(message: Message) -> None:
		await me(message)

	@dp.message(Command("requests"))
	async def list_requests(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		try:
			rows = api.get_list(
				"Service Request",
				fields=["name", "title", "status"],
				order_by="modified desc",
				limit_page_length=10,
			)
			if not rows:
				await message.answer("No ServiceRequest found.")
				return
			lines = [f"{r.get('name')}: {r.get('title','')[:60]} [{r.get('status','')}]" for r in rows]
			await message.answer("\n".join(lines))
		except Exception:
			logger.exception("list_requests failed")
			await message.answer("Failed to list requests (see logs).")

	@dp.message(Command("new_request"))
	async def new_request(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		title = (message.text or "").replace("/new_request", "", 1).strip()
		if not title:
			await message.answer("Usage: /new_request <title>")
			return
		try:
			company = settings.default_company
			if not company:
				companies = api.get_list(
					"Company",
					fields=["name"],
					order_by="name asc",
					limit_page_length=1,
				)
				company = (companies[0].get("name") if companies else None) or None
			doc = {
				"company": company,
				"title": title[:140],
				"status": "Open",
				"description": title,
			}
			if not doc.get("company"):
				await message.answer("Cannot create: missing default Company (set FERUM_DEFAULT_COMPANY).")
				return
			created = api.insert("Service Request", doc)
			await message.answer(f"Created ServiceRequest: {created.get('name')}")
		except Exception:
			logger.exception("create_request failed")
			await message.answer("Failed to create request (see logs).")

	@dp.message(Command("invoices"))
	async def invoices(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
			try:
				rows = api.get_list(
					"Invoice",
					fields=["name", "counterparty_name", "amount", "status"],
					order_by="modified desc",
					limit_page_length=10,
				)
				if not rows:
					await message.answer("No Invoice found.")
					return
				lines = [
					f"{r.get('name')}: {r.get('counterparty_name','')[:40]} {r.get('amount','')} [{r.get('status','')}]"
					for r in rows
				]
				await message.answer("\n".join(lines))
			except Exception:
				logger.exception("invoices failed")
				await message.answer("Failed to list invoices (see logs).")

	# Generic handler for unknown commands
	@dp.message(F.text.startswith("/"))
	async def unknown(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer("Unknown command. Use /help.")

	if settings.mode == "webhook":
		await _run_webhook(dp, bot, settings)
		return

	# Default to polling.
	await bot.delete_webhook(drop_pending_updates=True)
	await dp.start_polling(bot)


if __name__ == "__main__":
	asyncio.run(main())
