from __future__ import annotations

import time
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import BotCommand, Message

from ..frappe import FrappeAPI, FrappeAPIError
from ..settings import Settings


@dataclass
class _RegistrationCache:
	ttl_seconds: int = 60
	_cache: dict[int, tuple[float, bool]] | None = None

	def __post_init__(self) -> None:
		if self._cache is None:
			self._cache = {}

	def get(self, chat_id: int) -> bool | None:
		assert self._cache is not None
		entry = self._cache.get(chat_id)
		if not entry:
			return None
		expires_at, value = entry
		if expires_at < time.time():
			self._cache.pop(chat_id, None)
			return None
		return value

	def set(self, chat_id: int, value: bool) -> None:
		assert self._cache is not None
		self._cache[chat_id] = (time.time() + self.ttl_seconds, value)


def default_commands() -> list[BotCommand]:
	return [
		BotCommand(command="help", description="Справка"),
		BotCommand(command="chatid", description="Показать chat_id"),
		BotCommand(command="register", description="Привязать чат к пользователю ERP"),
		BotCommand(command="me", description="Проверка доступа к ERP API"),
		BotCommand(command="requests", description="Последние заявки"),
		BotCommand(command="new_request", description="Создать заявку"),
		BotCommand(command="invoices", description="Последние счета"),
	]


def build_router(settings: Settings, api: FrappeAPI | None) -> Router:
	router = Router(name="ferum_telegram_bot")
	reg_cache = _RegistrationCache()

	def _chat_allowed(message: Message) -> bool:
		if settings.allowed_chat_ids is None:
			return True
		try:
			return int(message.chat.id) in settings.allowed_chat_ids
		except Exception:
			return False

	async def _is_registered(chat_id: int) -> bool:
		cached = reg_cache.get(chat_id)
		if cached is not None:
			return cached
		if not api:
			reg_cache.set(chat_id, False)
			return False
		try:
			rows = await api.get_list(
				"Telegram User Link",
				fields=["name"],
				filters=[["chat_id", "=", str(chat_id)]],
				limit_page_length=1,
			)
			value = bool(rows)
			reg_cache.set(chat_id, value)
			return value
		except Exception:
			# Don't block usage if ERP is temporarily unavailable.
			return False

	def _erp_required_message() -> str:
		if settings.require_registration:
			return "Сначала зарегистрируйся: /register user@example.com"
		return "ERP API недоступен или не настроен."

	@router.message(CommandStart())
	async def start(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer("Ferum bot is online. Use /help for commands.")

	@router.message(Command("help"))
	async def help_cmd(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer(
			"/chatid — показать chat_id\n"
			"/register <user_email> — зарегистрировать чат/пользователя для уведомлений\n"
			"/me — проверка доступа к ERP API\n"
			"/requests — последние 10 Service Request\n"
			"/new_request <title> — создать Service Request\n"
			"/invoices — последние 10 Invoice\n"
		)

	@router.message(Command("chatid"))
	async def chatid(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer(
			f"chat_id={message.chat.id}\n"
			f"from=@{message.from_user.username if message.from_user else ''}\n"
		)

	@router.message(Command("me"))
	async def me(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		if settings.require_registration and not await _is_registered(message.chat.id):
			await message.answer(_erp_required_message())
			return
		try:
			# Prefer explicit method that returns current user (works with token auth).
			payload = await api.call("frappe.auth.get_logged_user")
			user = payload.get("message") or ""
			if user:
				await message.answer(f"ERP API: OK\nuser={user}")
				return
			# Fallback: simple list request to validate credentials.
			await api.get_list("User", fields=["name"], limit_page_length=1)
			await message.answer("ERP API: OK")
		except FrappeAPIError as e:
			await message.answer(f"ERP API: ERROR\n{e.status_code}: {e.message}")
		except Exception:
			await message.answer("ERP API: ERROR (see logs)")

	@router.message(Command("my"))
	async def my_alias(message: Message) -> None:
		await me(message)

	@router.message(Command("register"))
	async def register(message: Message, command: CommandObject) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		user_email = (command.args or "").strip()
		if not user_email:
			await message.answer("Usage: /register <user_email>")
			return
		try:
			# Validate user exists in ERP (User name is usually the email).
			await api.get_doc("User", user_email)
		except FrappeAPIError as e:
			if e.status_code == 404:
				await message.answer("ERP user not found. Проверь email и попробуй снова.")
				return
			await message.answer(f"Registration failed: {e.status_code}: {e.message}")
			return

		try:
			payload = {
				"user": user_email,
				"telegram_username": (message.from_user.username if message.from_user else "") or "",
				"chat_id": str(message.chat.id),
				"notes": f"tg_user_id={message.from_user.id if message.from_user else ''}",
			}

			existing = await api.get_list(
				"Telegram User Link",
				fields=["name", "user"],
				filters=[["chat_id", "=", str(message.chat.id)]],
				limit_page_length=1,
			)
			if existing:
				name = existing[0].get("name")
				updated = await api.update("Telegram User Link", str(name), payload)
				reg_cache.set(message.chat.id, True)
				await message.answer(f"Updated. Telegram User Link: {updated.get('name')}")
				return

			created = await api.insert("Telegram User Link", payload)
			reg_cache.set(message.chat.id, True)
			await message.answer(f"Registered. Telegram User Link: {created.get('name')}")
		except FrappeAPIError as e:
			await message.answer(f"Registration failed: {e.status_code}: {e.message}")
		except Exception:
			await message.answer("Registration failed (see logs).")

	@router.message(Command("requests"))
	async def list_requests(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		if settings.require_registration and not await _is_registered(message.chat.id):
			await message.answer(_erp_required_message())
			return
		try:
			rows = await api.get_list(
				"Service Request",
				fields=["name", "title", "status"],
				order_by="modified desc",
				limit_page_length=10,
			)
			if not rows:
				await message.answer("No Service Request found.")
				return
			lines = [f"{r.get('name')}: {str(r.get('title',''))[:60]} [{r.get('status','')}]" for r in rows]
			await message.answer("\n".join(lines))
		except FrappeAPIError as e:
			await message.answer(f"Failed to list requests: {e.status_code}: {e.message}")
		except Exception:
			await message.answer("Failed to list requests (see logs).")

	@router.message(Command("new_request"))
	async def new_request(message: Message, command: CommandObject) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		if settings.require_registration and not await _is_registered(message.chat.id):
			await message.answer(_erp_required_message())
			return

		title = (command.args or "").strip()
		if not title:
			await message.answer("Usage: /new_request <title>")
			return
		try:
			company = settings.default_company
			if not company:
				companies = await api.get_list(
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
			created = await api.insert("Service Request", doc)
			await message.answer(f"Created ServiceRequest: {created.get('name')}")
		except FrappeAPIError as e:
			await message.answer(f"Failed to create request: {e.status_code}: {e.message}")
		except Exception:
			await message.answer("Failed to create request (see logs).")

	@router.message(Command("invoices"))
	async def invoices(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer("ERP API is not configured.")
			return
		if settings.require_registration and not await _is_registered(message.chat.id):
			await message.answer(_erp_required_message())
			return
		try:
			rows = await api.get_list(
				"Invoice",
				fields=["name", "counterparty_name", "amount", "status"],
				order_by="modified desc",
				limit_page_length=10,
			)
			if not rows:
				await message.answer("No Invoice found.")
				return
			lines = [
				f"{r.get('name')}: {str(r.get('counterparty_name',''))[:40]} {r.get('amount','')} [{r.get('status','')}]"
				for r in rows
			]
			await message.answer("\n".join(lines))
		except FrappeAPIError as e:
			await message.answer(f"Failed to list invoices: {e.status_code}: {e.message}")
		except Exception:
			await message.answer("Failed to list invoices (see logs).")

	# Unknown commands
	@router.message(F.text.startswith("/"))
	async def unknown(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer("Unknown command. Use /help.")

	# Respond to any non-command message so users see the bot is alive.
	@router.message(~F.text.startswith("/"))
	async def fallback(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer("Я на связи. Команды: /help")

	return router

