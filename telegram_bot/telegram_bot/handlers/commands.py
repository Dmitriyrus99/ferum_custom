from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..frappe import FrappeAPI, FrappeAPIError
from ..settings import Settings


logger = logging.getLogger(__name__)


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
		BotCommand(command="register", description="Регистрация по email + коду"),
		BotCommand(command="me", description="Проверка доступа к ERP API"),
		BotCommand(command="projects", description="Мои проекты"),
		BotCommand(command="my_requests", description="Мои заявки (по проекту)"),
		BotCommand(command="attach", description="Прикрепить файл к заявке"),
		BotCommand(command="survey", description="Фото/чек-лист обследования"),
		BotCommand(command="subscribe", description="Подписаться на проект"),
		BotCommand(command="unsubscribe", description="Отписаться от проекта"),
		BotCommand(command="cancel", description="Отменить диалог"),
		BotCommand(command="requests", description="Последние заявки"),
		BotCommand(command="new_request", description="Создать заявку"),
		BotCommand(command="invoices", description="Последние счета"),
	]


def build_router(settings: Settings, api: FrappeAPI | None) -> Router:
	router = Router(name="ferum_telegram_bot")
	reg_cache = _RegistrationCache()

	_STATUS_RU = {
		# Keep wording aligned with Frappe/ERPNext Russian translations.
		"Open": "Открыт",
		"In Progress": "Выполняется",
		"Completed": "Завершенно",
		"Closed": "Закрыт",
		"Cancelled": "Отменен",
	}

	_PRIORITY_RU = {
		"Low": "Низкий",
		"Medium": "Средний",
		"High": "Высокий",
	}

	def _tr_status(value: str) -> str:
		return _STATUS_RU.get(value, value)

	def _tr_priority(value: str) -> str:
		return _PRIORITY_RU.get(value, value)

	def _project_label(row: dict) -> str:
		code = str(row.get("name") or "").strip()
		title = str(row.get("project_name") or "").strip()
		if title and title != code:
			return f"{code} — {title}"[:50]
		return (title or code or "—")[:50]

	def _request_label(row: dict) -> str:
		name = str(row.get("name") or "").strip()
		status = _tr_status(str(row.get("status") or "").strip())
		title = str(row.get("title") or "").strip()
		base = name
		if title:
			base = f"{name}: {title[:30]}"
		if status:
			base = f"{base} [{status}]"
		return base[:50] or name[:50] or "—"

	def _main_menu() -> ReplyKeyboardMarkup:
		return ReplyKeyboardMarkup(
			keyboard=[
				[KeyboardButton(text="🔗 Регистрация"), KeyboardButton(text="ℹ️ Помощь")],
				[KeyboardButton(text="🆕 Новая заявка"), KeyboardButton(text="📋 Мои заявки")],
				[KeyboardButton(text="📎 К заявке"), KeyboardButton(text="📁 Проекты")],
				[KeyboardButton(text="📷 Обследование"), KeyboardButton(text="🔔 Подписаться")],
				[KeyboardButton(text="🔕 Отписаться"), KeyboardButton(text="❌ Отмена")],
			],
			resize_keyboard=True,
			selective=True,
			)

	_MAIN_MENU_TEXTS = {
		"🔗 Регистрация",
		"ℹ️ Помощь",
		"🆕 Новая заявка",
		"📋 Мои заявки",
		"📎 К заявке",
		"📁 Проекты",
		"📷 Обследование",
		"🔔 Подписаться",
		"🔕 Отписаться",
		"❌ Отмена",
	}

	async def _skip_to_main_menu_if_pressed(message: Message, state: FSMContext) -> None:
		text = (message.text or "").strip()
		if text in _MAIN_MENU_TEXTS:
			# Drop current dialog state so the main-menu handlers can take over cleanly.
			await state.clear()
			raise SkipHandler

	class _NewRequest(StatesGroup):
		project = State()
		service_object = State()
		title = State()
		priority = State()
		description = State()
		confirm = State()

	class _MyRequestsPick(StatesGroup):
		project = State()

	class _PickProject(StatesGroup):
		pick = State()

	class _Register(StatesGroup):
		email = State()
		code = State()

	class _Survey(StatesGroup):
		project = State()
		service_object = State()
		section = State()
		upload = State()

	class _AttachRequest(StatesGroup):
		pick = State()
		upload = State()

	def _chat_allowed(message: Message) -> bool:
		# Access is controlled by registration + ERP permissions.
		# Allowed chat IDs are not enforced here to support customer self-registration via email+code.
		return True

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
		# New UX flows always need chat -> ERP user linkage.
		return "Сначала зарегистрируйся: /register user@example.com (на почту придёт код)"

	def _erp_unavailable_message() -> str:
		return "ERP API недоступен или не настроен."

	def _checklist_label(row: dict) -> str:
		section = str(row.get("section") or "").strip() or "—"
		required = bool(int(row.get("required") or 0))
		done = bool(int(row.get("done") or 0))
		prefix = "✅" if done else "⬜"
		if required:
			prefix += "*"
		return f"{prefix} {section}"[:50]

	async def _ensure_registered(message: Message) -> bool:
		if not api:
			await message.answer(_erp_unavailable_message())
			return False
		if not await _is_registered(message.chat.id):
			await message.answer(_erp_required_message())
			return False
		return True

	async def _get_active_project(chat_id: int) -> dict:
		if not api:
			return {"project": None}
		try:
			payload = await api.call_message(
				"ferum_custom.api.telegram_bot.get_active_project",
				{"chat_id": chat_id},
				http_method="GET",
			)
		except Exception:
			return {"project": None}
		return payload if isinstance(payload, dict) else {"project": None}

	async def _set_active_project(chat_id: int, project: str | None) -> None:
		assert api is not None
		await api.call_message(
			"ferum_custom.api.telegram_bot.set_active_project",
			{"chat_id": chat_id, "project": project},
			http_method="POST",
		)

	async def _choose_project(message: Message, state: FSMContext, *, prompt: str) -> None:
		assert api is not None
		projects = await api.call_message(
			"ferum_custom.api.telegram_bot.list_projects",
			{"chat_id": message.chat.id},
			http_method="GET",
		)
		if not projects:
			await message.answer("Нет доступных проектов. Попросите менеджера выдать доступ.")
			return
		await state.update_data(projects=projects)
		builder = InlineKeyboardBuilder()
		for idx, row in enumerate(projects[:20]):
			builder.button(text=_project_label(row), callback_data=f"nr_proj:{idx}")
		builder.adjust(1)
		await state.set_state(_NewRequest.project)
		await message.answer(prompt, reply_markup=builder.as_markup())

	async def _choose_object(message: Message, state: FSMContext, project: str) -> None:
		assert api is not None
		objects = await api.call_message(
			"ferum_custom.api.telegram_bot.list_objects",
			{"chat_id": message.chat.id, "project": project},
			http_method="GET",
		)
		if not objects:
			await state.clear()
			await message.answer(
				"В выбранном проекте нет объектов (Project Sites). Попроси менеджера проекта добавить объекты.",
				reply_markup=_main_menu(),
			)
			return
		await state.update_data(objects=objects, project=project)
		builder = InlineKeyboardBuilder()
		for idx, row in enumerate((objects or [])[:20]):
			name = str(row.get("name") or "")
			label = str(row.get("object_name") or name)
			builder.button(text=label[:50], callback_data=f"nr_obj:{idx}")
		builder.adjust(1)
		await state.set_state(_NewRequest.service_object)
		await message.answer("Выбери объект:", reply_markup=builder.as_markup())

	async def _choose_project_for_survey(message: Message, state: FSMContext, *, prompt: str) -> None:
		assert api is not None
		projects = await api.call_message(
			"ferum_custom.api.telegram_bot.list_projects",
			{"chat_id": message.chat.id},
			http_method="GET",
		)
		if not projects:
			await message.answer("Нет доступных проектов. Попросите менеджера выдать доступ.")
			return
		await state.update_data(projects=projects)
		builder = InlineKeyboardBuilder()
		for idx, row in enumerate(projects[:20]):
			builder.button(text=_project_label(row), callback_data=f"sv_proj:{idx}")
		builder.button(text="Отмена", callback_data="sv_cancel")
		builder.adjust(1)
		await state.set_state(_Survey.project)
		await message.answer(prompt, reply_markup=builder.as_markup())

	async def _choose_object_for_survey(message: Message, state: FSMContext, project: str) -> None:
		assert api is not None
		objects = await api.call_message(
			"ferum_custom.api.telegram_bot.list_objects",
			{"chat_id": message.chat.id, "project": project},
			http_method="GET",
		)
		if not objects:
			await state.clear()
			await message.answer(
				"В выбранном проекте нет объектов (Project Sites). Попроси менеджера проекта добавить объекты.",
				reply_markup=_main_menu(),
			)
			return
		await state.update_data(objects=objects, project=project)
		builder = InlineKeyboardBuilder()
		for idx, row in enumerate((objects or [])[:20]):
			name = str(row.get("name") or "")
			label = str(row.get("object_name") or name)
			builder.button(text=label[:50], callback_data=f"sv_obj:{idx}")
		builder.button(text="Отмена", callback_data="sv_cancel")
		builder.adjust(1)
		await state.set_state(_Survey.service_object)
		await message.answer("Выбери объект для обследования:", reply_markup=builder.as_markup())

	async def _show_survey_sections(message: Message, state: FSMContext, *, project: str) -> None:
		assert api is not None
		try:
			await api.call_message(
				"ferum_custom.api.telegram_bot.ensure_default_survey_checklist",
				{"chat_id": message.chat.id, "project": project},
				http_method="POST",
			)
		except Exception:
			# Best-effort: listing still works if checklist already exists.
			pass

		try:
			rows = await api.call_message(
				"ferum_custom.api.telegram_bot.get_survey_checklist",
				{"chat_id": message.chat.id, "project": project},
				http_method="GET",
			)
		except FrappeAPIError as e:
			await state.clear()
			await message.answer(f"Не удалось получить чек-лист: {e.status_code}: {e.message}", reply_markup=_main_menu())
			return
		except Exception:
			logger.exception("Failed to fetch survey checklist")
			await state.clear()
			await message.answer("Не удалось получить чек-лист (см. логи).", reply_markup=_main_menu())
			return
		rows = rows or []
		if not rows:
			await state.clear()
			await message.answer(
				"Чек-лист обследования пуст. Попроси менеджера проекта заполнить его в карточке проекта.",
				reply_markup=_main_menu(),
			)
			return
		await state.update_data(survey_rows=rows)
		builder = InlineKeyboardBuilder()
		for idx, row in enumerate(rows[:20]):
			builder.button(text=_checklist_label(row), callback_data=f"sv_sec:{idx}")
		builder.button(text="Отмена", callback_data="sv_cancel")
		builder.adjust(1)
		await state.set_state(_Survey.section)
		await message.answer("Выбери раздел чек-листа:", reply_markup=builder.as_markup())

	async def _start_registration(message: Message, *, user_email: str, state: FSMContext | None = None) -> None:
		assert api is not None
		user_email = (user_email or "").strip()
		if not user_email:
			await message.answer("Нужен email. Пример: /register user@example.com")
			return
		try:
			await api.call_message(
				"ferum_custom.api.telegram_bot.start_registration",
				{
					"chat_id": message.chat.id,
					"email": user_email,
					"telegram_username": (message.from_user.username if message.from_user else "") or "",
				},
				http_method="POST",
			)
		except FrappeAPIError as e:
			await message.answer(f"Не удалось отправить код: {e.status_code}: {e.message}")
			return
		if state:
			await state.update_data(register_email=user_email)
			await state.set_state(_Register.code)
		await message.answer("Код отправлен на email. Введите код одним сообщением (6 цифр).")

	async def _confirm_registration(message: Message, *, email: str, code: str) -> None:
		assert api is not None
		try:
			result = await api.call_message(
				"ferum_custom.api.telegram_bot.confirm_registration",
				{"chat_id": message.chat.id, "email": email, "code": code},
				http_method="POST",
			)
			reg_cache.set(message.chat.id, True)
			user = str((result or {}).get("user") or "")
			await message.answer(f"Готово. Чат привязан к пользователю ERP: {user}", reply_markup=_main_menu())
		except FrappeAPIError as e:
			await message.answer(f"Не удалось подтвердить: {e.status_code}: {e.message}")
		except Exception:
			logger.exception("Telegram registration confirm failed")
			await message.answer("Не удалось подтвердить (см. логи).")

	async def _pick_project(message: Message, state: FSMContext, *, prompt: str, action: str) -> None:
		assert api is not None
		projects = await api.call_message(
			"ferum_custom.api.telegram_bot.list_projects",
			{"chat_id": message.chat.id},
			http_method="GET",
		)
		if not projects:
			await message.answer("Нет доступных проектов. Попросите менеджера выдать доступ.")
			return
		await state.update_data(projects=projects, pick_action=action)
		builder = InlineKeyboardBuilder()
		for idx, row in enumerate(projects[:20]):
			builder.button(text=_project_label(row), callback_data=f"pick_proj:{idx}")
		builder.button(text="Отмена", callback_data="pick_cancel")
		builder.adjust(1)
		await state.set_state(_PickProject.pick)
		await message.answer(prompt, reply_markup=builder.as_markup())

	@router.message(CommandStart())
	async def start(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer(
			"Ferum bot is online.\n"
			"Если ты ещё не привязал чат — выполни /register user@example.com (получишь код на почту)\n"
			"Меню снизу.",
			reply_markup=_main_menu(),
		)

	@router.message(Command("help"))
	async def help_cmd(message: Message) -> None:
		if not _chat_allowed(message):
			return
		await message.answer(
			"/chatid — показать chat_id\n"
			"/register <email> — отправить код подтверждения на почту\n"
			"/register <email> <code> — подтвердить код и привязать чат\n"
			"/me — проверка доступа к ERP API\n"
			"/projects — выбрать активный проект\n"
			"/my_requests — мои заявки (по проекту)\n"
			"/attach — прикрепить фото/файл к заявке\n"
			"/survey — фото/чек-лист обследования\n"
			"/new_request — создать Service Request (диалог)\n"
			"/subscribe — подписаться на уведомления проекта\n"
			"/unsubscribe — отписаться от уведомлений проекта\n"
			"/cancel — отменить текущий диалог\n"
			"/requests — последние 10 Service Request (служебное)\n"
			"/invoices — последние 10 Invoice\n"
		)

	@router.message(F.text == "ℹ️ Помощь")
	async def help_btn(message: Message) -> None:
		await help_cmd(message)

	@router.message(Command("cancel"))
	async def cancel_cmd(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		await message.answer("Ок, отменено.", reply_markup=_main_menu())

	@router.message(F.text == "❌ Отмена")
	async def cancel_btn(message: Message, state: FSMContext) -> None:
		await cancel_cmd(message, state)

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
			await message.answer(_erp_unavailable_message())
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
	async def register(message: Message, command: CommandObject, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		args = (command.args or "").strip()
		parts = [p for p in args.split() if p.strip()] if args else []
		if not parts:
			await message.answer("Нужен email. Пример: /register user@example.com")
			return
		if len(parts) >= 2 and parts[1].isdigit():
			email = parts[0]
			code = parts[1]
			await _confirm_registration(message, email=email, code=code)
			return
		email = parts[0]
		await _start_registration(message, user_email=email, state=state)

	@router.message(F.text == "🔗 Регистрация")
	async def register_btn(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		await state.clear()
		await state.set_state(_Register.email)
		await message.answer("Отправь email (как в ERP / договоре), на него придёт код подтверждения.")

	@router.message(_Register.email)
	async def register_email(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await _skip_to_main_menu_if_pressed(message, state)
		if not api:
			await message.answer(_erp_unavailable_message())
			await state.clear()
			return
		await _start_registration(message, user_email=(message.text or "").strip(), state=state)

	@router.message(_Register.code)
	async def register_code(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await _skip_to_main_menu_if_pressed(message, state)
		if not api:
			await message.answer(_erp_unavailable_message())
			await state.clear()
			return
		code = (message.text or "").strip().replace(" ", "")
		data = await state.get_data()
		email = (data.get("register_email") or "").strip()
		if not email:
			await state.clear()
			await message.answer("Сначала зарегистрируйся: /register user@example.com")
			return
		if not code.isdigit() or len(code) < 4:
			await message.answer("Нужен код из письма (только цифры).")
			return
		await state.clear()
		await _confirm_registration(message, email=email, code=code)

	@router.message(Command("projects"))
	async def projects(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not await _ensure_registered(message):
			return
		active_payload = await _get_active_project(int(message.chat.id))
		active = str(active_payload.get("project") or "").strip() or None
		active_label = str(active_payload.get("project_name") or active or "").strip()
		prompt = "Выбери активный проект:"
		if active:
			prompt = f"Текущий активный проект: {active_label or active}\n\nВыбери другой проект:"
		assert api is not None
		await _pick_project(message, state, prompt=prompt, action="set_active")

	@router.message(F.text == "📁 Проекты")
	async def projects_btn(message: Message, state: FSMContext) -> None:
		await projects(message, state)

	@router.message(Command("survey"))
	async def survey_cmd(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not await _ensure_registered(message):
			return
		active_payload = await _get_active_project(int(message.chat.id))
		project = str(active_payload.get("project") or "").strip() or None
		if project:
			await state.update_data(project=project, project_label=str(active_payload.get("project_name") or project))
			await _choose_object_for_survey(message, state, project)
			return
		await _choose_project_for_survey(message, state, prompt="Выбери проект для обследования:")

	@router.message(F.text == "📷 Обследование")
	async def survey_btn(message: Message, state: FSMContext) -> None:
		await survey_cmd(message, state)

	async def _choose_request_for_attach(message: Message, state: FSMContext, *, project: str) -> None:
		assert api is not None
		rows = await api.call_message(
			"ferum_custom.api.telegram_bot.list_requests",
			{"chat_id": message.chat.id, "project": project, "limit": 10},
			http_method="GET",
		)
		rows = rows or []
		if not rows:
			await message.answer("Заявок не найдено.")
			return
		await state.update_data(attach_requests=rows, attach_project=project)
		builder = InlineKeyboardBuilder()
		for idx, row in enumerate(rows[:20]):
			builder.button(text=_request_label(row), callback_data=f"att_pick:{idx}")
		builder.button(text="Отмена", callback_data="att_cancel")
		builder.adjust(1)
		await state.set_state(_AttachRequest.pick)
		await message.answer("Выбери заявку:", reply_markup=builder.as_markup())

	async def _start_attach_for_request(message: Message, state: FSMContext, *, service_request: str) -> None:
		assert api is not None
		try:
			info = await api.call_message(
				"ferum_custom.api.telegram_bot.get_service_request",
				{"chat_id": message.chat.id, "service_request": service_request},
				http_method="GET",
			)
		except FrappeAPIError as e:
			await state.clear()
			await message.answer(f"Не удалось открыть заявку: {e.status_code}: {e.message}", reply_markup=_main_menu())
			return
		except Exception:
			logger.exception("Failed to load service request")
			await state.clear()
			await message.answer("Не удалось открыть заявку (см. логи).", reply_markup=_main_menu())
			return

		name = str((info or {}).get("name") or service_request).strip()
		title = str((info or {}).get("title") or "").strip()
		status = _tr_status(str((info or {}).get("status") or "").strip())
		url = str((info or {}).get("url") or "").strip()
		await state.update_data(service_request=name)
		await state.set_state(_AttachRequest.upload)
		await message.answer(
			f"Заявка: {name}\n"
			+ (f"Статус: {status}\n" if status else "")
			+ (f"{title}\n" if title else "")
			+ (f"{url}\n" if url else "")
			+ "\nОтправь фото/файлы. Когда закончишь — напиши «готово».\n"
			+ "Если не нужно — напиши «пропустить» (или «❌ Отмена»).",
			reply_markup=_main_menu(),
		)

	@router.message(Command("attach"))
	async def attach_cmd(message: Message, command: CommandObject, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not await _ensure_registered(message):
			return
		if not api:
			await message.answer(_erp_unavailable_message())
			return

		args = (command.args or "").strip()
		parts = [p for p in args.split() if p.strip()] if args else []
		if parts:
			await _start_attach_for_request(message, state, service_request=parts[0])
			return

		active_payload = await _get_active_project(int(message.chat.id))
		project = str(active_payload.get("project") or "").strip() or None
		if not project:
			await message.answer("Сначала выбери проект: /projects")
			return
		await _choose_request_for_attach(message, state, project=project)

	@router.message(F.text == "📎 К заявке")
	async def attach_btn(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not await _ensure_registered(message):
			return
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		active_payload = await _get_active_project(int(message.chat.id))
		project = str(active_payload.get("project") or "").strip() or None
		if not project:
			await message.answer("Сначала выбери проект: /projects")
			return
		await _choose_request_for_attach(message, state, project=project)

	@router.callback_query(F.data.startswith("att_pick:"))
	async def attach_pick_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		if not api:
			await query.answer()
			await state.clear()
			await message.answer(_erp_unavailable_message(), reply_markup=_main_menu())
			return

		data = await state.get_data()
		rows = data.get("attach_requests") or []
		project = str(data.get("attach_project") or "").strip()
		try:
			idx = int(str(query.data).split(":", 1)[1])
		except Exception:
			await query.answer()
			return

		# If state is stale, refetch using active project.
		if idx < 0 or idx >= len(rows):
			if not project:
				active_payload = await _get_active_project(int(message.chat.id))
				project = str(active_payload.get("project") or "").strip()
			if project:
				try:
					rows = await api.call_message(
						"ferum_custom.api.telegram_bot.list_requests",
						{"chat_id": message.chat.id, "project": project, "limit": 10},
						http_method="GET",
					)
					rows = rows or []
				except Exception:
					rows = []
		if idx < 0 or idx >= len(rows):
			await query.answer()
			await state.clear()
			await message.answer("Сессия выбора заявки устарела. Запусти /attach заново.", reply_markup=_main_menu())
			return

		req = rows[idx] or {}
		req_name = str(req.get("name") or "").strip()
		await query.answer()
		if not req_name:
			await state.clear()
			await message.answer("Не удалось определить заявку. Запусти /attach заново.", reply_markup=_main_menu())
			return
		await _start_attach_for_request(message, state, service_request=req_name)

	@router.callback_query(F.data == "att_cancel")
	async def attach_cancel(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		await query.answer()
		await state.clear()
		await message.answer("Отменено.", reply_markup=_main_menu())

	@router.message(_AttachRequest.upload, F.photo)
	async def attach_photo(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		data = await state.get_data()
		req_name = str(data.get("service_request") or "").strip()
		if not req_name:
			await state.clear()
			await message.answer("Сначала выбери заявку: /attach", reply_markup=_main_menu())
			return
		photo = (message.photo or [])[-1]
		try:
			result = await api.call_message(
				"ferum_custom.api.telegram_bot.upload_service_request_attachment",
				{
					"chat_id": message.chat.id,
					"service_request": req_name,
					"telegram_file_id": photo.file_id,
				},
				http_method="POST",
				timeout=120.0,
			)
			await state.update_data(last_folder_url=str((result or {}).get("folder_url") or ""))
			await message.answer(f"Загружено: {str((result or {}).get('file_url') or '')}")
		except FrappeAPIError as e:
			await message.answer(f"Не удалось загрузить: {e.status_code}: {e.message}")
		except Exception:
			logger.exception("Request attachment photo upload failed")
			await message.answer("Не удалось загрузить (см. логи).")

	@router.message(_AttachRequest.upload, F.document)
	async def attach_document(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		data = await state.get_data()
		req_name = str(data.get("service_request") or "").strip()
		doc = message.document
		if not req_name or not doc:
			await state.clear()
			await message.answer("Сначала выбери заявку: /attach", reply_markup=_main_menu())
			return
		try:
			result = await api.call_message(
				"ferum_custom.api.telegram_bot.upload_service_request_attachment",
				{
					"chat_id": message.chat.id,
					"service_request": req_name,
					"telegram_file_id": doc.file_id,
					"telegram_file_name": doc.file_name,
				},
				http_method="POST",
				timeout=120.0,
			)
			await state.update_data(last_folder_url=str((result or {}).get("folder_url") or ""))
			await message.answer(f"Загружено: {str((result or {}).get('file_url') or '')}")
		except FrappeAPIError as e:
			await message.answer(f"Не удалось загрузить: {e.status_code}: {e.message}")
		except Exception:
			logger.exception("Request attachment document upload failed")
			await message.answer("Не удалось загрузить (см. логи).")

	@router.message(_AttachRequest.upload, F.text)
	async def attach_text(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await _skip_to_main_menu_if_pressed(message, state)
		text = (message.text or "").strip().lower()
		if text in {"готово", "готово.", "done", "ok", "ок", "✅"}:
			data = await state.get_data()
			folder = str(data.get("last_folder_url") or "").strip()
			await state.clear()
			await message.answer(("Ок. Папка заявки:\n" + folder) if folder else "Ок.", reply_markup=_main_menu())
			return
		if text in {"пропустить", "skip"}:
			await state.clear()
			await message.answer("Ок.", reply_markup=_main_menu())
			return
		await message.answer("Отправь фото/файл или напиши «готово»/«пропустить» (или «❌ Отмена»).")

	@router.message(Command("my_requests"))
	async def my_requests(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not await _ensure_registered(message):
			return
		active_payload = await _get_active_project(int(message.chat.id))
		project = str(active_payload.get("project") or "").strip() or None
		if not project:
			assert api is not None
			projects = await api.call_message(
				"ferum_custom.api.telegram_bot.list_projects",
				{"chat_id": message.chat.id},
				http_method="GET",
			)
			if not projects:
				await message.answer("Нет доступных проектов.")
				return
			await state.update_data(projects=projects)
			builder = InlineKeyboardBuilder()
			for idx, row in enumerate(projects[:20]):
				builder.button(text=_project_label(row), callback_data=f"mr_proj:{idx}")
			builder.adjust(1)
			await state.set_state(_MyRequestsPick.project)
			await message.answer("Выбери проект для списка заявок:", reply_markup=builder.as_markup())
			return
		assert api is not None
		rows = await api.call_message(
			"ferum_custom.api.telegram_bot.list_requests",
			{"chat_id": message.chat.id, "project": project, "limit": 10},
			http_method="GET",
		)
		if not rows:
			await message.answer(f"Заявок по проекту {project} не найдено.")
			return
		lines = [
			f"{r.get('name')}: {str(r.get('title',''))[:60]} [{_tr_status(str(r.get('status','') or '').strip())}]"
			for r in rows
		]
		await message.answer(
			"\n".join(lines) + "\n\nЧтобы прикрепить файлы: /attach <ID> или кнопка «📎 К заявке».",
			reply_markup=_main_menu(),
		)

	@router.callback_query(F.data.startswith("mr_proj:"))
	async def mr_project_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		if await state.get_state() != _MyRequestsPick.project.state:
			await query.answer()
			return
		data = await state.get_data()
		projects = data.get("projects") or []
		try:
			idx = int(str(query.data).split(":", 1)[1])
		except Exception:
			await query.answer()
			return
		if idx < 0 or idx >= len(projects):
			await query.answer()
			return
		project = str(projects[idx].get("name") or "")
		project_label = _project_label(projects[idx])
		if not project:
			await query.answer()
			return
		await query.answer()
		await state.clear()
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		try:
			try:
				await _set_active_project(int(message.chat.id), project)
			except Exception:
				# Best-effort: if ERP temporarily fails, still return list.
				pass

			rows = await api.call_message(
				"ferum_custom.api.telegram_bot.list_requests",
				{"chat_id": message.chat.id, "project": project, "limit": 10},
				http_method="GET",
			)
			if not rows:
				await message.answer(f"Заявок по проекту {project_label} не найдено.")
				return
			lines = [
				f"{r.get('name')}: {str(r.get('title',''))[:60]} [{_tr_status(str(r.get('status','') or '').strip())}]"
				for r in rows
			]
			await message.answer(
				f"{project_label}\n\n"
				+ "\n".join(lines)
				+ "\n\nЧтобы прикрепить файлы: /attach <ID> или кнопка «📎 К заявке».",
				reply_markup=_main_menu(),
			)
		except FrappeAPIError as e:
			await message.answer(f"Не удалось получить заявки: {e.status_code}: {e.message}")
		except Exception:
			logger.exception("Failed to list my requests for selected project")
			await message.answer("Не удалось получить заявки (см. логи).")

	@router.message(Command("subscribe"))
	async def subscribe(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not await _ensure_registered(message):
			return
		assert api is not None
		active_payload = await _get_active_project(int(message.chat.id))
		active_project = str(active_payload.get("project") or "").strip() or None
		active_label = str(active_payload.get("project_name") or active_project or "").strip()
		if active_project:
			try:
				await api.call_message(
					"ferum_custom.api.telegram_bot.subscribe_project",
					{"chat_id": message.chat.id, "project": active_project},
					http_method="POST",
				)
				await message.answer(
					f"Подписка на проект {active_label or active_project}: OK",
					reply_markup=_main_menu(),
				)
			except FrappeAPIError as e:
				await message.answer(f"Операция не выполнена: {e.status_code}: {e.message}", reply_markup=_main_menu())
			except Exception:
				logger.exception("Subscribe active project failed")
				await message.answer("Операция не выполнена (см. логи).", reply_markup=_main_menu())
			return
		await _pick_project(message, state, prompt="Выбери проект для подписки:", action="subscribe")

	@router.message(F.text == "🔔 Подписаться")
	async def subscribe_btn(message: Message, state: FSMContext) -> None:
		await subscribe(message, state)

	@router.message(Command("unsubscribe"))
	async def unsubscribe(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not await _ensure_registered(message):
			return
		assert api is not None
		active_payload = await _get_active_project(int(message.chat.id))
		active_project = str(active_payload.get("project") or "").strip() or None
		active_label = str(active_payload.get("project_name") or active_project or "").strip()
		if active_project:
			try:
				await api.call_message(
					"ferum_custom.api.telegram_bot.unsubscribe_project",
					{"chat_id": message.chat.id, "project": active_project},
					http_method="POST",
				)
				await message.answer(
					f"Подписка на проект {active_label or active_project}: отключена",
					reply_markup=_main_menu(),
				)
			except FrappeAPIError as e:
				await message.answer(f"Операция не выполнена: {e.status_code}: {e.message}", reply_markup=_main_menu())
			except Exception:
				logger.exception("Unsubscribe active project failed")
				await message.answer("Операция не выполнена (см. логи).", reply_markup=_main_menu())
			return
		await _pick_project(message, state, prompt="Выбери проект для отписки:", action="unsubscribe")

	@router.message(F.text == "🔕 Отписаться")
	async def unsubscribe_btn(message: Message, state: FSMContext) -> None:
		await unsubscribe(message, state)

	@router.callback_query(F.data.startswith("pick_proj:"))
	async def pick_project_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		if await state.get_state() != _PickProject.pick.state:
			await query.answer()
			return
		data = await state.get_data()
		projects = data.get("projects") or []
		action = str(data.get("pick_action") or "")
		try:
			idx = int(str(query.data).split(":", 1)[1])
		except Exception:
			await query.answer()
			return
		if idx < 0 or idx >= len(projects):
			await query.answer()
			return
		project = str(projects[idx].get("name") or "")
		project_label = _project_label(projects[idx])
		if not project:
			await query.answer()
			return

		await query.answer()
		await state.clear()
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		try:
			if action == "subscribe":
				await api.call_message(
					"ferum_custom.api.telegram_bot.subscribe_project",
					{"chat_id": message.chat.id, "project": project},
					http_method="POST",
				)
				try:
					await _set_active_project(int(message.chat.id), project)
				except Exception:
					pass
				await message.answer(f"Подписка на проект {project_label}: OK", reply_markup=_main_menu())
				return
			if action == "unsubscribe":
				await api.call_message(
					"ferum_custom.api.telegram_bot.unsubscribe_project",
					{"chat_id": message.chat.id, "project": project},
					http_method="POST",
				)
				try:
					await _set_active_project(int(message.chat.id), project)
				except Exception:
					pass
				await message.answer(f"Подписка на проект {project_label}: отключена", reply_markup=_main_menu())
				return
			# Default action: store active project on ERP side.
			await _set_active_project(int(message.chat.id), project)
			await message.answer(f"Активный проект: {project_label}", reply_markup=_main_menu())
		except FrappeAPIError as e:
			await message.answer(f"Операция не выполнена: {e.status_code}: {e.message}", reply_markup=_main_menu())
		except Exception:
			logger.exception("Pick project action failed")
			await message.answer("Операция не выполнена (см. логи).", reply_markup=_main_menu())

	@router.callback_query(F.data == "pick_cancel")
	async def pick_cancel(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		await query.answer()
		await state.clear()
		await message.answer("Отменено.", reply_markup=_main_menu())

	@router.message(Command("requests"))
	async def list_requests(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not await _ensure_registered(message):
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
			lines = [
				f"{r.get('name')}: {str(r.get('title',''))[:60]} [{_tr_status(str(r.get('status','') or '').strip())}]"
				for r in rows
			]
			await message.answer("\n".join(lines))
		except FrappeAPIError as e:
			await message.answer(f"Failed to list requests: {e.status_code}: {e.message}")
		except Exception:
			await message.answer("Failed to list requests (see logs).")

	@router.message(Command("new_request"))
	async def new_request(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await state.clear()
		if not await _ensure_registered(message):
			return
		active_payload = await _get_active_project(int(message.chat.id))
		project = str(active_payload.get("project") or "").strip() or None
		if project:
			await state.update_data(
				project=project,
				project_label=str(active_payload.get("project_name") or project),
			)
			await _choose_object(message, state, project)
			return
		await _choose_project(message, state, prompt="Выбери проект для новой заявки:")

	@router.message(F.text == "🆕 Новая заявка")
	async def new_request_btn(message: Message, state: FSMContext) -> None:
		await new_request(message, state)

	@router.message(F.text == "📋 Мои заявки")
	async def my_requests_btn(message: Message, state: FSMContext) -> None:
		await my_requests(message, state)

	@router.callback_query(F.data.startswith("nr_proj:"))
	async def nr_project_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		data = await state.get_data()
		projects = data.get("projects") or []
		try:
			idx = int(str(query.data).split(":", 1)[1])
		except Exception:
			await query.answer()
			return
		if idx < 0 or idx >= len(projects):
			await query.answer()
			return
		project = str(projects[idx].get("name") or "")
		project_label = str(projects[idx].get("project_name") or project)
		if not project:
			await query.answer()
			return
		if api:
			try:
				await _set_active_project(int(message.chat.id), project)
			except Exception:
				# Best-effort: do not block request creation if saving active project fails.
				pass
		await state.update_data(project=project, project_label=project_label)
		await query.answer()
		await _choose_object(message, state, project)

	@router.callback_query(F.data.startswith("sv_proj:"))
	async def sv_project_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		data = await state.get_data()
		try:
			idx = int(str(query.data).split(":", 1)[1])
		except Exception:
			await query.answer()
			return
		assert api is not None
		projects = data.get("projects") or []
		if idx < 0 or idx >= len(projects):
			try:
				projects = await api.call_message(
					"ferum_custom.api.telegram_bot.list_projects",
					{"chat_id": message.chat.id},
					http_method="GET",
				)
				projects = projects or []
			except Exception:
				projects = []
		if idx < 0 or idx >= len(projects):
			await query.answer()
			await state.clear()
			await message.answer("Сессия выбора проекта устарела. Запусти /survey заново.", reply_markup=_main_menu())
			return
		project = str((projects[idx] or {}).get("name") or "")
		project_label = str((projects[idx] or {}).get("project_name") or project)
		if not project:
			await query.answer()
			return
		if api:
			try:
				await _set_active_project(int(message.chat.id), project)
			except Exception:
				pass
		await state.update_data(project=project, project_label=project_label)
		await query.answer()
		await _choose_object_for_survey(message, state, project)

	@router.callback_query(F.data.startswith("sv_obj:"))
	async def sv_object_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		data = await state.get_data()
		try:
			idx = int(str(query.data).split(":", 1)[1])
		except Exception:
			await query.answer()
			return
		assert api is not None
		project = str(data.get("project") or "").strip()
		if not project:
			active_payload = await _get_active_project(int(message.chat.id))
			project = str(active_payload.get("project") or "").strip()
		if not project:
			await query.answer()
			await state.clear()
			await message.answer("Сначала выбери проект: /survey", reply_markup=_main_menu())
			return

		objects = data.get("objects") or []
		if idx < 0 or idx >= len(objects):
			try:
				objects = await api.call_message(
					"ferum_custom.api.telegram_bot.list_objects",
					{"chat_id": message.chat.id, "project": project},
					http_method="GET",
				)
				objects = objects or []
			except Exception:
				objects = []
		if idx < 0 or idx >= len(objects):
			await query.answer()
			await state.clear()
			await message.answer("Сессия выбора объекта устарела. Запусти /survey заново.", reply_markup=_main_menu())
			return

		obj = objects[idx] or {}
		obj_name = str(obj.get("name") or "")
		obj_label = str(obj.get("object_name") or obj_name)
		if not obj_name or not project:
			await query.answer()
			return
		await state.update_data(project=project, objects=objects, service_object=obj_name, service_object_label=obj_label)
		await query.answer()
		await _show_survey_sections(message, state, project=project)

	@router.callback_query(F.data.startswith("sv_sec:"))
	async def sv_section_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		data = await state.get_data()
		try:
			idx = int(str(query.data).split(":", 1)[1])
		except Exception:
			await query.answer()
			return
		assert api is not None
		project = str(data.get("project") or "").strip()
		if not project:
			active_payload = await _get_active_project(int(message.chat.id))
			project = str(active_payload.get("project") or "").strip()
		if not project:
			await query.answer()
			await state.clear()
			await message.answer("Сначала выбери проект: /survey", reply_markup=_main_menu())
			return

		rows = data.get("survey_rows") or []
		if idx < 0 or idx >= len(rows):
			try:
				rows = await api.call_message(
					"ferum_custom.api.telegram_bot.get_survey_checklist",
					{"chat_id": message.chat.id, "project": project},
					http_method="GET",
				)
				rows = rows or []
			except Exception:
				rows = []
		if idx < 0 or idx >= len(rows):
			await query.answer()
			await state.clear()
			await message.answer("Сессия выбора раздела устарела. Запусти /survey заново.", reply_markup=_main_menu())
			return

		row = rows[idx] or {}
		section = str(row.get("section") or "").strip()
		if not section:
			await query.answer()
			return
			await state.update_data(project=project, survey_rows=rows, survey_section=section)
			await query.answer()
			await state.set_state(_Survey.upload)
			await message.answer(
				f"Раздел: {section}\n\n"
				"Отправь фото/файлы сообщениями в этот чат.\n"
				"Когда закончишь — напиши «готово» (или «❌ Отмена»).",
				reply_markup=_main_menu(),
			)

	@router.message(_Survey.upload, F.photo)
	async def sv_upload_photo(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		data = await state.get_data()
		project = str(data.get("project") or "")
		obj = str(data.get("service_object") or "")
		section = str(data.get("survey_section") or "")
		if not project or not obj or not section:
			await state.clear()
			await message.answer("Сессия обследования устарела. Запусти /survey заново.", reply_markup=_main_menu())
			return
		photo = (message.photo or [])[-1]
		try:
			result = await api.call_message(
				"ferum_custom.api.telegram_bot.upload_survey_evidence",
				{
					"chat_id": message.chat.id,
					"project": project,
					"project_site": obj,
					"section": section,
					"telegram_file_id": photo.file_id,
				},
				http_method="POST",
				timeout=120.0,
			)
			await state.update_data(last_folder_url=str((result or {}).get("folder_url") or ""))
			await message.answer(f"Загружено: {str((result or {}).get('file_url') or '')}")
		except FrappeAPIError as e:
			await message.answer(f"Не удалось загрузить: {e.status_code}: {e.message}")
		except Exception:
			logger.exception("Survey photo upload failed")
			await message.answer("Не удалось загрузить (см. логи).")

	@router.message(_Survey.upload, F.document)
	async def sv_upload_document(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		if not api:
			await message.answer(_erp_unavailable_message())
			return
		data = await state.get_data()
		project = str(data.get("project") or "")
		obj = str(data.get("service_object") or "")
		section = str(data.get("survey_section") or "")
		doc = message.document
		if not project or not obj or not section or not doc:
			await state.clear()
			await message.answer("Сессия обследования устарела. Запусти /survey заново.", reply_markup=_main_menu())
			return
		try:
			result = await api.call_message(
				"ferum_custom.api.telegram_bot.upload_survey_evidence",
				{
					"chat_id": message.chat.id,
					"project": project,
					"project_site": obj,
					"section": section,
					"telegram_file_id": doc.file_id,
					"telegram_file_name": doc.file_name,
				},
				http_method="POST",
				timeout=120.0,
			)
			await state.update_data(last_folder_url=str((result or {}).get("folder_url") or ""))
			await message.answer(f"Загружено: {str((result or {}).get('file_url') or '')}")
		except FrappeAPIError as e:
			await message.answer(f"Не удалось загрузить: {e.status_code}: {e.message}")
		except Exception:
			logger.exception("Survey document upload failed")
			await message.answer("Не удалось загрузить (см. логи).")

	@router.message(_Survey.upload, F.text)
	async def sv_upload_text(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await _skip_to_main_menu_if_pressed(message, state)
		text = (message.text or "").strip().lower()
		if text in {"готово", "готово.", "done", "ok", "ок", "✅"}:
			data = await state.get_data()
			folder = str(data.get("last_folder_url") or "").strip()
			await state.clear()
			await message.answer(("Ок. Папка раздела:\n" + folder) if folder else "Ок.", reply_markup=_main_menu())
			return
		await message.answer("Отправь фото/файл или напиши «готово» (или «❌ Отмена»).")

	@router.callback_query(F.data == "sv_cancel")
	async def sv_cancel(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		await query.answer()
		await state.clear()
		await message.answer("Отменено.", reply_markup=_main_menu())

	@router.callback_query(F.data.startswith("nr_obj:"))
	async def nr_object_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		data = await state.get_data()
		objects = data.get("objects") or []
		try:
			idx = int(str(query.data).split(":", 1)[1])
		except Exception:
			await query.answer()
			return
		if idx < 0 or idx >= len(objects):
			await query.answer()
			return
		service_object = str(objects[idx].get("name") or "")
		service_object_label = str(objects[idx].get("object_name") or service_object)
		if not service_object:
			await query.answer()
			return
		await state.update_data(service_object=service_object, service_object_label=service_object_label)
		await state.set_state(_NewRequest.title)
		await query.answer()
		await message.answer("Опиши проблему одним сообщением (заголовок заявки):")

	@router.message(_NewRequest.title)
	async def nr_title(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await _skip_to_main_menu_if_pressed(message, state)
		title = (message.text or "").strip()
		if not title:
			await message.answer("Нужен текст заголовка.")
			return
		await state.update_data(title=title)
		await state.set_state(_NewRequest.priority)
		builder = InlineKeyboardBuilder()
		for p in ["Low", "Medium", "High"]:
			builder.button(text=_tr_priority(p), callback_data=f"nr_pri:{p}")
		builder.adjust(3)
		await message.answer("Приоритет:", reply_markup=builder.as_markup())

	@router.callback_query(F.data.startswith("nr_pri:"))
	async def nr_priority_selected(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		priority = str(query.data).split(":", 1)[1].strip()
		if priority not in {"Low", "Medium", "High"}:
			await query.answer()
			return
		await state.update_data(priority=priority)
		await state.set_state(_NewRequest.description)
		await query.answer()
		await message.answer("Добавь описание (или /skip):")

	@router.message(Command("skip"))
	async def skip(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		if await state.get_state() != _NewRequest.description.state:
			return
		await state.update_data(description="")
		await state.set_state(_NewRequest.confirm)
		data = await state.get_data()
		builder = InlineKeyboardBuilder()
		builder.button(text="Создать", callback_data="nr_confirm:yes")
		builder.button(text="Отмена", callback_data="nr_confirm:no")
		builder.adjust(2)
		await message.answer(
			f"Создать заявку?\n"
			f"Проект: {data.get('project_label') or data.get('project')}\n"
			f"Объект: {data.get('service_object_label') or data.get('service_object')}\n"
			f"Приоритет: {_tr_priority(str(data.get('priority') or ''))}\n"
			f"Заголовок: {data.get('title')}",
			reply_markup=builder.as_markup(),
		)

	@router.message(_NewRequest.description)
	async def nr_description(message: Message, state: FSMContext) -> None:
		if not _chat_allowed(message):
			return
		await _skip_to_main_menu_if_pressed(message, state)
		desc = (message.text or "").strip()
		await state.update_data(description=desc)
		await state.set_state(_NewRequest.confirm)
		data = await state.get_data()
		builder = InlineKeyboardBuilder()
		builder.button(text="Создать", callback_data="nr_confirm:yes")
		builder.button(text="Отмена", callback_data="nr_confirm:no")
		builder.adjust(2)
		await message.answer(
			f"Создать заявку?\n"
			f"Проект: {data.get('project_label') or data.get('project')}\n"
			f"Объект: {data.get('service_object_label') or data.get('service_object')}\n"
			f"Приоритет: {_tr_priority(str(data.get('priority') or ''))}\n"
			f"Заголовок: {data.get('title')}\n"
			f"Описание: {(data.get('description') or '')[:200]}",
			reply_markup=builder.as_markup(),
		)

	@router.callback_query(F.data.startswith("nr_confirm:"))
	async def nr_confirm(query, state: FSMContext) -> None:
		message = getattr(query, "message", None)
		if not message or not _chat_allowed(message):
			return
		action = str(query.data).split(":", 1)[1]
		await query.answer()
		if action != "yes":
			await state.clear()
			await message.answer("Отменено.")
			return
		if not api:
			await message.answer(_erp_unavailable_message())
			await state.clear()
			return
		data = await state.get_data()
		try:
			result = await api.call_message(
				"ferum_custom.api.telegram_bot.create_service_request",
				{
					"chat_id": message.chat.id,
					"project": data.get("project"),
					"service_object": data.get("service_object"),
					"title": data.get("title"),
					"description": data.get("description"),
					"priority": data.get("priority"),
				},
				http_method="POST",
			)
			req_name = str((result or {}).get("name") or "").strip()
			req_url = str((result or {}).get("url") or "").strip()
			await message.answer(f"Заявка создана: {req_name}\n{req_url}".strip())
			await state.clear()
			if req_name:
				await _start_attach_for_request(message, state, service_request=req_name)
				return
		except FrappeAPIError as e:
			await state.clear()
			await message.answer(f"Не удалось создать: {e.status_code}: {e.message}")
		except Exception:
			await state.clear()
			await message.answer("Не удалось создать заявку (см. логи).")
		return

	@router.message(Command("invoices"))
	async def invoices(message: Message) -> None:
		if not _chat_allowed(message):
			return
		if not await _ensure_registered(message):
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
