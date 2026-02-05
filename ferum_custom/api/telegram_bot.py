from __future__ import annotations

import hashlib
import os
import re
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, cint, get_url, now_datetime, validate_email_address

_DOTENV_LOADED = False


def _ensure_dotenv_loaded() -> None:
	"""Load bench `.env` for long-running processes where env vars may not be passed explicitly."""
	global _DOTENV_LOADED
	if _DOTENV_LOADED:
		return
	_DOTENV_LOADED = True
	try:
		from dotenv import load_dotenv  # type: ignore
	except Exception:
		return

	for parent in Path(__file__).resolve().parents[:8]:
		candidate = parent / ".env"
		if candidate.exists():
			load_dotenv(dotenv_path=str(candidate), override=False)
			return


def _get_conf(key: str) -> str | None:
	_ensure_dotenv_loaded()
	val = frappe.conf.get(key) if hasattr(frappe, "conf") else None
	if val is None:
		val = os.getenv(key)
	if val is None:
		return None
	val = str(val).strip()
	return val or None


def _telegram_bot_token() -> str | None:
	# Prefer env/site_config over DocType settings.
	token = _get_conf("FERUM_TELEGRAM_BOT_TOKEN") or _get_conf("TELEGRAM_BOT_TOKEN")
	return token or None


def _drive_folder_id_from_url(url: str | None) -> str | None:
	url = str(url or "").strip()
	if not url:
		return None
	m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
	return m.group(1) if m else None


def _safe_filename(name: str) -> str:
	name = (name or "").strip().replace("\n", " ").replace("\r", " ")
	name = re.sub(r"[\\\\/\\0<>:\"|?*]+", "_", name)
	name = re.sub(r"\\s+", " ", name).strip()
	return name[:180] or "file"


def _telegram_fetch_file(*, token: str, file_id: str) -> tuple[str, str]:
	file_id = str(file_id or "").strip()
	if not file_id:
		raise ValueError("file_id is empty")

	r = requests.get(
		f"https://api.telegram.org/bot{token}/getFile",
		params={"file_id": file_id},
		timeout=20,
	)
	r.raise_for_status()
	payload = r.json() if r.content else {}
	if not isinstance(payload, dict) or not payload.get("ok"):
		raise ValueError("Telegram getFile failed")
	result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
	file_path = str((result or {}).get("file_path") or "").strip()
	if not file_path:
		raise ValueError("Telegram getFile returned empty file_path")

	download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
	suggested_name = os.path.basename(file_path) or "file"
	return download_url, suggested_name


def _download_to_tempfile(url: str, *, suffix: str = "") -> str:
	url = str(url or "").strip()
	if not url:
		raise ValueError("url is empty")
	with requests.get(url, stream=True, timeout=60) as r:
		r.raise_for_status()
		with tempfile.NamedTemporaryFile(prefix="tg_", suffix=suffix, delete=False) as tmp:
			for chunk in r.iter_content(chunk_size=1024 * 1024):
				if chunk:
					tmp.write(chunk)
				return tmp.name


def _safe_requests_error_summary(exc: Exception) -> str:
	"""Return a safe short summary for requests exceptions without leaking URLs/tokens."""
	status = None
	try:
		resp = getattr(exc, "response", None)
		status = getattr(resp, "status_code", None)
	except Exception:
		status = None
	return f"{type(exc).__name__}" + (f" (status={status})" if status else "")


@dataclass(frozen=True)
class LinkedTelegramUser:
	name: str
	user: str
	chat_id: int


def _has_role(role: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	try:
		return role in set(frappe.get_roles(user))
	except Exception:
		return False


def _require_system_manager() -> None:
	# We run bot requests using a service token; keep endpoints private.
	if frappe.session.user == "Guest" or not _has_role("System Manager"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _service_request_meta():
	return frappe.get_meta("Service Request")


def _project_meta():
	return frappe.get_meta("Project")


def _project_site_dt() -> str:
	return "Project Site"


def _normalize_email(raw: str | None) -> str:
	return (raw or "").strip().lower()


def _resolve_user_by_email(email: str) -> str | None:
	email = _normalize_email(email)
	if not email:
		return None
	if frappe.db.exists("User", email):
		return email
	name = frappe.db.get_value("User", {"email": email}, "name")
	return str(name) if name else None


def _customer_projects_by_email(email: str) -> list[str]:
	"""Return verified projects where email appears in Project customer_contacts table."""
	email = _normalize_email(email)
	if not email:
		return []
	if not frappe.db.exists("DocType", "Project Customer Contact"):
		return []
	rows = frappe.get_all(
		"Project Customer Contact",
		filters={
			"parenttype": "Project",
			"official_email": email,
			"official_email_verified": 1,
		},
		pluck="parent",
		limit=500,
	)
	return [str(p) for p in rows if p]


def _hash_verification_code(*, salt: str, email: str, chat_id: int, code: str) -> str:
	payload = f"{salt}:{_normalize_email(email)}:{int(chat_id)}:{str(code).strip()}"
	return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _send_verification_email(*, email: str, code: str, ttl_minutes: int) -> None:
	subject = _("Код подтверждения Ferum bot")
	message = _(
		"Ваш код подтверждения для Ferum bot: {0}\n\n"
		"Срок действия: {1} мин.\n"
		"Если вы не запрашивали код — просто проигнорируйте это письмо."
	).format(code, ttl_minutes)
	frappe.sendmail(recipients=[email], subject=subject, message=message, delayed=False)


def _rate_limit_key(*, email: str, chat_id: int) -> str:
	return f"ferum:tg:reg:{int(chat_id)}:{_normalize_email(email)}"


def _check_rate_limit(*, email: str, chat_id: int, min_seconds: int = 60) -> None:
	"""Best-effort anti-spam for code sending."""
	try:
		cache = frappe.cache()
		keys = [
			_rate_limit_key(email=email, chat_id=chat_id),
			f"ferum:tg:reg:email:{_normalize_email(email)}",
		]
		if any(cache.get_value(k) for k in keys):
			frappe.throw(_("Код уже отправлен недавно. Подожди минуту и попробуй снова."))
		for k in keys:
			cache.set_value(k, "1", expires_in_sec=int(min_seconds))
	except Exception:
		# Don't block registration if cache is unavailable.
		return


def _expire_pending_verifications(*, email: str, chat_id: int, purpose: str) -> None:
	try:
		frappe.db.sql(
			"""
			update `tabTelegram Email Verification`
			set status = 'Expired'
			where email = %(email)s
			  and chat_id = %(chat_id)s
			  and purpose = %(purpose)s
			  and status = 'Pending'
			""",
			{"email": _normalize_email(email), "chat_id": str(int(chat_id)), "purpose": str(purpose)},
		)
	except Exception:
		# Best-effort: expiration is not critical for correct behavior.
		return


def _resolve_link(chat_id: int) -> LinkedTelegramUser:
	row = frappe.get_all(
		"Telegram User Link",
		filters={"chat_id": str(chat_id)},
		fields=["name", "user", "chat_id"],
		limit=1,
	)
	if not row:
		frappe.throw(_("Chat is not registered. Use /register <user_email> in Telegram first."))

	user = (row[0].get("user") or "").strip()
	if not user:
		frappe.throw(_("Chat is not registered correctly (missing ERP user)."))
	return LinkedTelegramUser(name=row[0]["name"], user=user, chat_id=cint(row[0]["chat_id"]))


def _as_user(user: str):
	class _Ctx:
		def __enter__(self):
			self._prev = frappe.session.user
			frappe.set_user(user)
			return self

		def __exit__(self, exc_type, exc, tb):
			frappe.set_user(self._prev)
			return False

	return _Ctx()


def _user_permissions(user: str, allow: str) -> set[str]:
	if not frappe.db.exists("DocType", "User Permission"):
		return set()
	rows = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": allow},
		pluck="for_value",
		limit=2000,
	)
	return {str(v) for v in rows if v}


def _customers_from_contact_user(user: str) -> set[str]:
	"""Resolve Customer list from Contact.user -> Contact.links (Dynamic Link)."""
	if not frappe.db.exists("DocType", "Contact") or not frappe.db.exists("DocType", "Dynamic Link"):
		return set()
	contacts = frappe.get_all("Contact", filters={"user": user}, pluck="name", limit=200)
	if not contacts:
		return set()
	customers = frappe.get_all(
		"Dynamic Link",
		filters={
			"parenttype": "Contact",
			"parent": ["in", list(contacts)],
			"link_doctype": "Customer",
		},
		pluck="link_name",
		limit=500,
	)
	return {str(c) for c in customers if c}


def _projects_for_link(link: LinkedTelegramUser) -> list[dict]:
	if not frappe.db.exists("DocType", "Project"):
		return []

	project_meta = _project_meta()
	project_fields = ["name"]
	for fn in ["project_name", "customer", "project_manager", "ferum_stage", "status", "company"]:
		if project_meta.has_field(fn):
			project_fields.append(fn)

	# System Manager gets full access by default.
	if _has_role("System Manager", link.user):
		return frappe.get_all(
			"Project",
			fields=project_fields,
			limit=500,
			order_by="modified desc",
		)

	projects: set[str] = set()

	# Direct roles on project
	if project_meta.has_field("project_manager"):
		projects.update(
			frappe.get_all(
				"Project",
				filters={"project_manager": link.user},
				pluck="name",
				limit=500,
			)
		)

	# Engineer access via Project Site.default_engineer
	if frappe.db.exists("DocType", _project_site_dt()) and frappe.db.has_column(
		_project_site_dt(), "default_engineer"
	):
		rows = frappe.db.sql(
			"""
			select distinct parent
			from `tabProject Site`
			where parenttype = 'Project'
			  and ifnull(default_engineer,'') = %(user)s
			limit 500
			""",
			{"user": link.user},
		)
		projects.update({str(r[0]) for r in rows if r and r[0]})

	# Explicit subscriptions (telegram_users child table)
	rows = frappe.get_all(
		"Project Telegram User Item",
		filters={"telegram_user": link.name, "parenttype": "Project"},
		pluck="parent",
		limit=500,
	)
	projects.update(rows)

	# User Permission: Project
	projects.update(_user_permissions(link.user, "Project"))

	# User Permission: Customer -> include projects by customer
	customers = _user_permissions(link.user, "Customer")
	customers.update(_customers_from_contact_user(link.user))
	if customers and project_meta.has_field("customer"):
		projects.update(
			frappe.get_all(
				"Project",
				filters={"customer": ["in", list(customers)]},
				pluck="name",
				limit=500,
			)
		)

	if not projects:
		return []

	return frappe.get_all(
		"Project",
		filters={"name": ["in", list(projects)]},
		fields=project_fields,
		limit=500,
		order_by="modified desc",
	)


def _assert_project_access(link: LinkedTelegramUser, project: str) -> None:
	allowed = {p["name"] for p in _projects_for_link(link)}
	if project not in allowed:
		frappe.throw(_("No access to project {0}.").format(project), frappe.PermissionError)


def _is_engineer_scoped_user(user: str) -> bool:
	"""Whether this user should see only their assigned objects within a project."""
	roles = set(frappe.get_roles(user) or [])
	if "System Manager" in roles:
		return False
	# Privileged roles can view all objects.
	if roles.intersection(
		{
			"Project Manager",
			"Projects Manager",
			"Office Manager",
			"Ferum Office Manager",
			"Ferum Director",
			"Ferum Tender Specialist",
			"General Director",
		}
	):
		return False
	return "Service Engineer" in roles


def _service_request_filters_for_project(project: str) -> dict:
	meta = _service_request_meta()
	if meta.has_field("erp_project") and frappe.db.has_column("Service Request", "erp_project"):
		return {"erp_project": project}
	# Legacy
	if meta.has_field("project") and frappe.db.has_column("Service Request", "project"):
		return {"project": project}
	return {}


@frappe.whitelist()
@frappe.read_only()
def list_projects(chat_id: int) -> list[dict]:
	_require_system_manager()
	link = _resolve_link(chat_id)
	return _projects_for_link(link)


@frappe.whitelist(methods=["POST"])
def start_registration(chat_id: int, *, email: str, telegram_username: str | None = None) -> dict:
	"""Start registration by sending a verification code to the provided email."""
	_require_system_manager()
	email = _normalize_email(email)
	validate_email_address(email, throw=True)
	chat_id = cint(chat_id)
	if not chat_id:
		frappe.throw(_("Missing chat_id."))

	# Prevent sending codes to arbitrary emails: allow only known internal users or verified project contacts.
	user = _resolve_user_by_email(email)
	projects = [] if user else _customer_projects_by_email(email)
	if not user and not projects:
		frappe.throw(
			_(
				"Email не найден.\n"
				"Для заказчика: добавьте email в Проект → Контакты заказчика и отметьте «Email проверен».\n"
				"Для сотрудника: email должен существовать в ERP как пользователь."
			)
		)

	_check_rate_limit(email=email, chat_id=chat_id, min_seconds=60)
	_expire_pending_verifications(email=email, chat_id=chat_id, purpose="registration")

	ttl_minutes = 10
	code = f"{secrets.randbelow(1_000_000):06d}"
	salt = frappe.generate_hash(length=12)
	code_hash = _hash_verification_code(salt=salt, email=email, chat_id=chat_id, code=code)
	expires_at = add_to_date(now_datetime(), minutes=ttl_minutes)

	# Persist request before/after sending email: keep consistent behavior.
	try:
		_send_verification_email(email=email, code=code, ttl_minutes=ttl_minutes)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Telegram registration email send failed")
		frappe.throw(_("Не удалось отправить письмо с кодом. Проверьте настройки исходящей почты в ERP."))

	doc = frappe.get_doc(
		{
			"doctype": "Telegram Email Verification",
			"email": email,
			"chat_id": str(chat_id),
			"telegram_username": (telegram_username or "").strip(),
			"purpose": "registration",
			"status": "Pending",
			"expires_at": expires_at,
			"attempts": 0,
			"erp_user": user,
			"code_hash": code_hash,
			"code_salt": salt,
		}
	)
	doc.insert(ignore_permissions=True)

	return {"ok": True, "email": email, "expires_in_minutes": ttl_minutes}


def _ensure_project_permissions(user: str, projects: list[str]) -> None:
	projects = [p for p in (projects or []) if p]
	if not projects:
		return
	for project in projects:
		if frappe.db.exists(
			"User Permission",
			{"user": user, "allow": "Project", "for_value": project},
		):
			continue
		up = frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user,
				"allow": "Project",
				"for_value": project,
				"apply_to_all_doctypes": 0,
			}
		)
		up.insert(ignore_permissions=True)


def _ensure_portal_user(email: str) -> str:
	email = _normalize_email(email)
	if not email:
		frappe.throw(_("Missing email."))
	if frappe.db.exists("User", email):
		return email

	user = frappe.new_doc("User")
	user.email = email
	user.first_name = email.split("@", 1)[0][:50] or email
	user.enabled = 1
	user.user_type = "Website User"
	user.flags.no_welcome_mail = True
	user.insert(ignore_permissions=True)

	try:
		doc = frappe.get_doc("User", email)
		doc.add_roles("Client")
		doc.save(ignore_permissions=True)
	except Exception:
		# Role might not exist in some setups; keep portal user anyway.
		frappe.log_error(frappe.get_traceback(), "Failed to assign Client role to portal user")

	return email


@frappe.whitelist(methods=["POST"])
def confirm_registration(chat_id: int, *, email: str, code: str) -> dict:
	"""Confirm registration by verifying email code and creating Telegram User Link."""
	_require_system_manager()
	email = _normalize_email(email)
	validate_email_address(email, throw=True)
	chat_id = cint(chat_id)
	code = (code or "").strip()
	if not chat_id:
		frappe.throw(_("Missing chat_id."))
	if not code or not code.isdigit():
		frappe.throw(_("Неверный код."))

	now = now_datetime()
	rows = frappe.get_all(
		"Telegram Email Verification",
		filters={
			"email": email,
			"chat_id": str(chat_id),
			"purpose": "registration",
			"status": "Pending",
			"expires_at": (">=", now),
		},
		fields=["name", "code_hash", "code_salt", "attempts", "erp_user", "expires_at"],
		limit=1,
		order_by="modified desc",
	)
	if not rows:
		frappe.throw(_("Код не найден или истёк. Повтори /register и запроси новый код."))

	row = rows[0]
	verification = frappe.get_doc("Telegram Email Verification", row["name"])
	attempts = cint(getattr(verification, "attempts", 0) or 0)
	if attempts >= 5:
		verification.status = "Locked"
		verification.save(ignore_permissions=True)
		frappe.throw(_("Слишком много попыток. Запроси новый код через /register."))

	expected = str(getattr(verification, "code_hash", "") or "")
	salt = str(getattr(verification, "code_salt", "") or "")
	actual = _hash_verification_code(salt=salt, email=email, chat_id=chat_id, code=code)
	if not expected or actual != expected:
		verification.attempts = attempts + 1
		if cint(verification.attempts) >= 5:
			verification.status = "Locked"
		verification.save(ignore_permissions=True)
		frappe.throw(_("Неверный код."))

	verification.status = "Verified"
	verification.verified_at = now
	verification.save(ignore_permissions=True)

	user = (getattr(verification, "erp_user", None) or "").strip() or _resolve_user_by_email(email)
	is_portal = False
	projects: list[str] = []
	if not user:
		projects = _customer_projects_by_email(email)
		if not projects:
			frappe.throw(_("Email не найден в подтверждённых контактах проекта."))
		user = _ensure_portal_user(email)
		is_portal = True
		_ensure_project_permissions(user, projects)

	# Create/update Telegram User Link.
	existing = frappe.get_all(
		"Telegram User Link",
		filters={"chat_id": str(chat_id)},
		fields=["name"],
		limit=1,
	)
	if existing:
		link = frappe.get_doc("Telegram User Link", existing[0]["name"])
		link.user = user
		if getattr(verification, "telegram_username", None):
			link.telegram_username = verification.telegram_username
		# If a user had an active project stored, keep it.
		link.save(ignore_permissions=True)
	else:
		link = frappe.get_doc(
			{
				"doctype": "Telegram User Link",
				"user": user,
				"telegram_username": (getattr(verification, "telegram_username", None) or "").strip(),
				"chat_id": str(chat_id),
				"notes": f"verified_email={email}",
			}
		)
		link.insert(ignore_permissions=True)

	# Convenience: if only one project is granted (portal users), set it as active.
	try:
		if (
			link.meta.has_field("active_project")
			and not getattr(link, "active_project", None)
			and len(projects) == 1
		):
			frappe.db.set_value(
				"Telegram User Link",
				link.name,
				"active_project",
				projects[0],
				update_modified=True,
			)
	except Exception:
		pass

	return {
		"ok": True,
		"user": user,
		"chat_id": chat_id,
		"email": email,
		"is_portal_user": bool(is_portal),
		"projects_granted": projects,
	}


@frappe.whitelist()
@frappe.read_only()
def get_active_project(chat_id: int) -> dict:
	"""Return active project for this chat (stored on Telegram User Link)."""
	_require_system_manager()
	link = _resolve_link(chat_id)
	meta = frappe.get_meta("Telegram User Link")
	if not meta.has_field("active_project"):
		return {"project": None}

	active = frappe.db.get_value("Telegram User Link", link.name, "active_project")
	active = (active or "").strip()
	if not active:
		return {"project": None}

	try:
		_assert_project_access(link, active)
	except Exception:
		# If permissions changed, clear invalid active project.
		try:
			frappe.db.set_value(
				"Telegram User Link", link.name, "active_project", None, update_modified=False
			)
		except Exception:
			pass
		return {"project": None}

	payload: dict = {"project": active}
	project_meta = _project_meta()
	if project_meta.has_field("project_name"):
		payload["project_name"] = frappe.db.get_value("Project", active, "project_name")
	if project_meta.has_field("ferum_stage"):
		payload["ferum_stage"] = frappe.db.get_value("Project", active, "ferum_stage")
	return payload


@frappe.whitelist(methods=["POST"])
def set_active_project(chat_id: int, project: str | None = None) -> dict:
	"""Set active project for this chat (stored on Telegram User Link)."""
	_require_system_manager()
	link = _resolve_link(chat_id)
	meta = frappe.get_meta("Telegram User Link")
	if not meta.has_field("active_project"):
		frappe.throw(_("Active project is not configured."))

	project = (project or "").strip()
	if not project:
		frappe.db.set_value("Telegram User Link", link.name, "active_project", None, update_modified=True)
		return {"ok": True, "project": None}

	_assert_project_access(link, project)
	frappe.db.set_value("Telegram User Link", link.name, "active_project", project, update_modified=True)
	return {"ok": True, "project": project}


@frappe.whitelist()
@frappe.read_only()
def list_objects(chat_id: int, project: str) -> list[dict]:
	_require_system_manager()
	link = _resolve_link(chat_id)
	_assert_project_access(link, project)
	if not frappe.db.exists("DocType", _project_site_dt()):
		return []
	engineer_only = _is_engineer_scoped_user(link.user)
	rows = frappe.get_all(
		_project_site_dt(),
		filters={
			"parenttype": "Project",
			"parent": project,
			**({"default_engineer": link.user} if engineer_only else {}),
		},
		fields=["name", "site_name", "address", "default_engineer", "idx"],
		limit=500,
		order_by="idx asc",
	)
	# Preserve legacy keys expected by bot UI: object_name/address/default_engineer.
	out: list[dict] = []
	for r in rows:
		out.append(
			{
				"name": r.get("name"),
				"object_name": r.get("site_name"),
				"address": r.get("address"),
				"default_engineer": r.get("default_engineer"),
			}
		)
	return out


@frappe.whitelist()
@frappe.read_only()
def list_requests(chat_id: int, project: str | None = None, limit: int = 10) -> list[dict]:
	_require_system_manager()
	link = _resolve_link(chat_id)

	filters: dict = {}
	if project:
		_assert_project_access(link, project)
		filters.update(_service_request_filters_for_project(project))

	# For client users, default to customer-wide visibility within accessible projects.
	meta = _service_request_meta()
	if _has_role("Client", link.user) and not _has_role("System Manager", link.user):
		# If we can infer customer(s), use them to avoid leaking unrelated records.
		customers = _customers_from_contact_user(link.user) | _user_permissions(link.user, "Customer")
		if meta.has_field("customer") and customers:
			filters["customer"] = ["in", list(customers)]
		else:
			# Conservative fallback: show only user's own requests.
			filters["owner"] = link.user

	return frappe.get_all(
		"Service Request",
		filters=filters,
		fields=[
			"name",
			"title",
			"status",
			"priority",
			"erp_project",
			"project_site",
			"assigned_to",
			"modified",
		],
		limit=cint(limit) or 10,
		order_by="modified desc",
	)


@frappe.whitelist(methods=["POST"])
def create_service_request(
	chat_id: int,
	*,
	project: str,
	project_site: str | None = None,
	service_object: str | None = None,  # backward compatible: treat as project_site
	title: str,
	description: str | None = None,
	priority: str | None = None,
	request_type: str | None = None,
) -> dict:
	_require_system_manager()
	link = _resolve_link(chat_id)
	_assert_project_access(link, project)

	if not title or not str(title).strip():
		frappe.throw(_("Missing title."))

	site = (project_site or service_object or "").strip()
	if not site:
		frappe.throw(_("Missing project_site."))

	if not frappe.db.exists(_project_site_dt(), site):
		frappe.throw(_("Project Site not found."))
	site_doc = frappe.get_doc(_project_site_dt(), site)
	if getattr(site_doc, "parenttype", None) != "Project" or getattr(site_doc, "parent", None) != project:
		frappe.throw(_("Project Site does not belong to selected Project."))

	project_doc = frappe.get_doc("Project", project)
	project_meta = _project_meta()
	company = getattr(project_doc, "company", None) if project_meta.has_field("company") else None
	customer = getattr(project_doc, "customer", None) if project_meta.has_field("customer") else None
	engineer = getattr(site_doc, "default_engineer", None)

	with _as_user(link.user):
		meta = _service_request_meta()
		values: dict = {
			"doctype": "Service Request",
			"title": str(title).strip()[:140],
			"status": "Open",
			"description": (description or str(title).strip()),
			"priority": priority or "Medium",
			"type": request_type or "Routine Maintenance",
		}
		if meta.has_field("company") and company:
			values["company"] = company
		if meta.has_field("customer") and customer:
			values["customer"] = customer
		if meta.has_field("erp_project"):
			values["erp_project"] = project
		if meta.has_field("project_site"):
			values["project_site"] = site
		if meta.has_field("assigned_to") and engineer:
			values["assigned_to"] = engineer

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)

	url = get_url(f"/app/service-request/{doc.name}")
	return {
		"name": doc.name,
		"url": url,
		"assigned_to": getattr(doc, "assigned_to", None),
		"project": project,
		"project_site": site,
	}


@frappe.whitelist(methods=["POST"])
def subscribe_project(chat_id: int, project: str) -> dict:
	_require_system_manager()
	link = _resolve_link(chat_id)
	_assert_project_access(link, project)

	row_exists = frappe.get_all(
		"Project Telegram User Item",
		filters={"parenttype": "Project", "parent": project, "telegram_user": link.name},
		pluck="name",
		limit=1,
	)
	if row_exists:
		return {"ok": True, "subscribed": True}

	with _as_user("Administrator"):
		p = frappe.get_doc("Project", project)
		if not p.meta.has_field("telegram_users"):
			frappe.throw(_("Project subscriptions are not configured."))
		p.append("telegram_users", {"telegram_user": link.name})
		p.save(ignore_permissions=True)
	return {"ok": True, "subscribed": True}


@frappe.whitelist(methods=["POST"])
def unsubscribe_project(chat_id: int, project: str) -> dict:
	_require_system_manager()
	link = _resolve_link(chat_id)
	_assert_project_access(link, project)

	with _as_user("Administrator"):
		p = frappe.get_doc("Project", project)
		if not p.meta.has_field("telegram_users"):
			return {"ok": True, "subscribed": False}
		removed = False
		for row in list(p.get("telegram_users") or []):
			if getattr(row, "telegram_user", None) == link.name:
				p.remove(row)
				removed = True
		if removed:
			p.save(ignore_permissions=True)
	return {"ok": True, "subscribed": False}


def _survey_checklist_dt() -> str:
	return "Project Survey Checklist Item"


_DEFAULT_SURVEY_SECTIONS: list[str] = [
	"ППКП/АРМ",
	"Датчики",
	"Газ",
	"Порошок",
	"Насосная",
	"Документация/Шлейфы",
]


@frappe.whitelist(methods=["POST"])
def ensure_default_survey_checklist(chat_id: int, project: str) -> dict:
	"""Create default survey checklist rows for a project (best-effort).

	This does NOT save the Project doc (to avoid P0 stage gate validations).
	It inserts child rows directly into `Project Survey Checklist Item`.
	"""
	_require_system_manager()
	link = _resolve_link(chat_id)
	project = (project or "").strip()
	if not project:
		frappe.throw(_("Missing project."))
	_assert_project_access(link, project)

	if not frappe.db.exists("DocType", _survey_checklist_dt()):
		return {"ok": True, "created": 0}

	existing_rows = frappe.get_all(
		_survey_checklist_dt(),
		filters={"parenttype": "Project", "parent": project, "parentfield": "survey_checklist"},
		fields=["section", "idx"],
		limit=200,
	)
	existing_sections = {str(r.get("section") or "").strip() for r in existing_rows if r.get("section")}
	max_idx = 0
	for r in existing_rows:
		try:
			max_idx = max(max_idx, int(r.get("idx") or 0))
		except Exception:
			continue

	created = 0
	for section in _DEFAULT_SURVEY_SECTIONS:
		if section in existing_sections:
			continue
		max_idx += 1
		row = frappe.get_doc(
			{
				"doctype": _survey_checklist_dt(),
				"parenttype": "Project",
				"parent": project,
				"parentfield": "survey_checklist",
				"idx": max_idx,
				"section": section,
				"required": 1,
				"done": 0,
				"evidence_link": "",
			}
		)
		row.insert(ignore_permissions=True)
		created += 1

	return {"ok": True, "created": created}


@frappe.whitelist()
@frappe.read_only()
def get_survey_checklist(chat_id: int, project: str) -> list[dict]:
	_require_system_manager()
	link = _resolve_link(chat_id)
	project = (project or "").strip()
	if not project:
		frappe.throw(_("Missing project."))
	_assert_project_access(link, project)

	if not frappe.db.exists("DocType", _survey_checklist_dt()):
		return []

	return frappe.get_all(
		_survey_checklist_dt(),
		filters={"parenttype": "Project", "parent": project, "parentfield": "survey_checklist"},
		fields=["name", "idx", "section", "required", "done", "evidence_link"],
		limit=200,
		order_by="idx asc",
	)


@frappe.whitelist(methods=["POST"])
def upload_survey_evidence(
	chat_id: int,
	*,
	project: str,
	project_site: str,
	section: str,
	telegram_file_id: str,
	telegram_file_name: str | None = None,
) -> dict:
	"""Upload a Telegram file into Google Drive object folder and link it to survey checklist.

	- Ensures Drive folders exist for the Project + its objects.
	- Creates/uses a subfolder under object folder for the checklist section.
	- Uploads the file and sets `Project Survey Checklist Item.evidence_link` to the section folder url.
	"""
	_require_system_manager()
	link = _resolve_link(chat_id)

	project = (project or "").strip()
	project_site = (project_site or "").strip()
	section = (section or "").strip()
	telegram_file_id = (telegram_file_id or "").strip()
	telegram_file_name = (telegram_file_name or "").strip() if telegram_file_name else None

	if not project:
		frappe.throw(_("Missing project."))
	if not project_site:
		frappe.throw(_("Missing project_site."))
	if not section:
		frappe.throw(_("Missing section."))
	if not telegram_file_id:
		frappe.throw(_("Missing telegram_file_id."))

	_assert_project_access(link, project)
	if not frappe.db.exists(_project_site_dt(), project_site):
		frappe.throw(_("Project Site not found."))
	site_parent = frappe.db.get_value(_project_site_dt(), project_site, "parent")
	if str(site_parent or "").strip() != project:
		frappe.throw(_("Project Site does not belong to selected Project."))

	# Ensure Drive folders exist (idempotent).
	try:
		from ferum_custom.api.project_drive import ensure_drive_folders

		ensure_drive_folders(project)
	except Exception:
		# Keep any exceptions user-friendly (project_drive already does), but log traceback here.
		frappe.log_error(
			title="Ferum: upload_survey_evidence ensure_drive_folders", message=frappe.get_traceback()
		)
		raise

	site_folder_url = frappe.db.get_value(_project_site_dt(), project_site, "drive_folder_url")
	site_folder_id = _drive_folder_id_from_url(site_folder_url)
	if not site_folder_id:
		frappe.throw(_("Drive folder for this object is not configured. Create Drive folders first."))

	token = _telegram_bot_token()
	if not token:
		frappe.throw(_("Telegram bot token is not configured on server."))

	try:
		download_url, suggested_name = _telegram_fetch_file(token=token, file_id=telegram_file_id)
	except requests.RequestException as e:
		# Do not log traceback: it may contain full Telegram API URLs with bot token.
		frappe.log_error(title="Ferum: Telegram getFile failed", message=_safe_requests_error_summary(e))
		raise frappe.ValidationError(
			_("Не удалось получить файл из Telegram. Попробуйте отправить файл ещё раз.")
		) from None
	except Exception as e:
		frappe.log_error(title="Ferum: Telegram getFile failed", message=_safe_requests_error_summary(e))
		raise frappe.ValidationError(_("Не удалось получить файл из Telegram.")) from None
	base_name = telegram_file_name or suggested_name
	base_name = _safe_filename(base_name)
	suffix = os.path.splitext(suggested_name)[1] or os.path.splitext(base_name)[1]

	tmp_path = ""
	try:
		try:
			tmp_path = _download_to_tempfile(download_url, suffix=suffix)
		except requests.RequestException as e:
			# Do not log traceback: it may contain full Telegram API URLs with bot token.
			frappe.log_error(
				title="Ferum: Telegram file download failed", message=_safe_requests_error_summary(e)
			)
			raise frappe.ValidationError(
				_("Не удалось скачать файл из Telegram. Попробуйте отправить файл ещё раз.")
			) from None

		from ferum_custom.integrations.google_drive_folders import (
			ensure_folder,
			get_drive_service,
			upload_file,
		)

		service = get_drive_service()
		survey_root = ensure_folder(service, name="01_ОБСЛЕДОВАНИЕ", parent_id=site_folder_id)
		try:
			idx = _DEFAULT_SURVEY_SECTIONS.index(section) + 1
			section_folder_name = f"{idx:02d}_{_safe_filename(section)}"
		except Exception:
			section_folder_name = f"99_{_safe_filename(section)}"
		section_folder = ensure_folder(service, name=section_folder_name[:120], parent_id=survey_root.id)
		file_name = base_name if base_name.lower().endswith(suffix.lower()) else f"{base_name}{suffix}"
		drive_file = upload_file(service, local_path=tmp_path, parent_id=section_folder.id, name=file_name)

		# Link checklist item to the section folder (so multiple files can be uploaded).
		row_name = frappe.get_all(
			_survey_checklist_dt(),
			filters={
				"parenttype": "Project",
				"parent": project,
				"parentfield": "survey_checklist",
				"section": section,
			},
			pluck="name",
			limit=1,
		)
		if row_name:
			frappe.db.set_value(
				_survey_checklist_dt(),
				row_name[0],
				"evidence_link",
				section_folder.web_view_link,
				update_modified=False,
			)
			frappe.db.set_value(_survey_checklist_dt(), row_name[0], "done", 1, update_modified=False)
		else:
			row = frappe.get_doc(
				{
					"doctype": _survey_checklist_dt(),
					"parenttype": "Project",
					"parent": project,
					"parentfield": "survey_checklist",
					"section": section,
					"required": 1,
					"done": 1,
					"evidence_link": section_folder.web_view_link,
				}
			)
			row.insert(ignore_permissions=True)

		try:
			with _as_user("Administrator"):
				p = frappe.get_doc("Project", project)
				p.add_comment(
					"Info",
					f"Обследование: {section}\nФайл: {file_name}\n{drive_file.web_view_link or ''}",
				)
		except Exception:
			# Best-effort: don't fail the whole upload because of comment permission.
			frappe.log_error(
				title="Ferum: upload_survey_evidence add_comment", message=frappe.get_traceback()
			)

		return {
			"ok": True,
			"project": project,
			"project_site": project_site,
			"section": section,
			"folder_url": section_folder.web_view_link,
			"file_url": drive_file.web_view_link,
			"file_name": file_name,
		}
	finally:
		if tmp_path:
			try:
				os.remove(tmp_path)
			except Exception:
				pass


def _service_request_dt_name(name: str) -> str:
	"""Resolve Service Request doctype for this site (new vs legacy naming)."""
	name = (name or "").strip()
	if not name:
		frappe.throw(_("Missing service request id."))
	if frappe.db.exists("DocType", "Service Request") and frappe.db.exists("Service Request", name):
		return "Service Request"
	if frappe.db.exists("DocType", "ServiceRequest") and frappe.db.exists("ServiceRequest", name):
		return "ServiceRequest"
	if frappe.db.exists("DocType", "Service Request"):
		return "Service Request"
	return "ServiceRequest"


def _service_request_project_and_site(doc) -> tuple[str | None, str | None]:
	meta = _service_request_meta()
	project = None
	if meta.has_field("erp_project") and frappe.db.has_column(meta.name, "erp_project"):
		project = (getattr(doc, "erp_project", None) or "").strip() or None
	if not project and meta.has_field("project") and frappe.db.has_column(meta.name, "project"):
		project = (getattr(doc, "project", None) or "").strip() or None

	site = None
	if meta.has_field("project_site") and frappe.db.has_column(meta.name, "project_site"):
		site = (getattr(doc, "project_site", None) or "").strip() or None
	if not site and meta.has_field("service_object") and frappe.db.has_column(meta.name, "service_object"):
		# Legacy: Service Object id (not Project Site)
		site = (getattr(doc, "service_object", None) or "").strip() or None

	return project, site


def _assert_service_request_access(link: LinkedTelegramUser, doc) -> tuple[str, str | None]:
	project, site = _service_request_project_and_site(doc)
	if not project:
		frappe.throw(_("Service Request is not linked to a Project."))

	_assert_project_access(link, project)

	# Engineer-scoped users can operate only within their assigned objects/requests.
	if _is_engineer_scoped_user(link.user) and not _has_role("System Manager", link.user):
		assigned_to = (getattr(doc, "assigned_to", None) or "").strip()
		if assigned_to and assigned_to == link.user:
			return project, site
		if (
			site
			and frappe.db.exists("DocType", _project_site_dt())
			and frappe.db.exists(_project_site_dt(), site)
		):
			engineer = frappe.db.get_value(_project_site_dt(), site, "default_engineer")
			if str(engineer or "").strip() == link.user:
				return project, site
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	# Clients should not be able to touch unrelated customers' requests.
	if _has_role("Client", link.user) and not _has_role("System Manager", link.user):
		meta = _service_request_meta()
		customers = _customers_from_contact_user(link.user) | _user_permissions(link.user, "Customer")
		if meta.has_field("customer") and customers:
			customer = (getattr(doc, "customer", None) or "").strip()
			if customer and customer in customers:
				return project, site
		if (getattr(doc, "owner", None) or "").strip() == link.user:
			return project, site
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	return project, site


@frappe.whitelist()
@frappe.read_only()
def get_service_request(chat_id: int, service_request: str) -> dict:
	"""Return a Service Request summary for bot UI (with access checks)."""
	_require_system_manager()
	link = _resolve_link(chat_id)
	service_request = (service_request or "").strip()
	dt = _service_request_dt_name(service_request)
	doc = frappe.get_doc(dt, service_request)
	project, site = _assert_service_request_access(link, doc)
	url = get_url(f"/app/service-request/{doc.name}")
	return {
		"name": doc.name,
		"title": getattr(doc, "title", None),
		"status": getattr(doc, "status", None),
		"priority": getattr(doc, "priority", None),
		"assigned_to": getattr(doc, "assigned_to", None),
		"project": project,
		"project_site": site,
		"url": url,
	}


@frappe.whitelist(methods=["POST"])
def upload_service_request_attachment(
	chat_id: int,
	*,
	service_request: str,
	telegram_file_id: str,
	telegram_file_name: str | None = None,
) -> dict:
	"""Upload a Telegram file into Google Drive request folder and comment the request."""
	_require_system_manager()
	link = _resolve_link(chat_id)

	service_request = (service_request or "").strip()
	telegram_file_id = (telegram_file_id or "").strip()
	telegram_file_name = (telegram_file_name or "").strip() if telegram_file_name else None
	if not service_request:
		frappe.throw(_("Missing service_request."))
	if not telegram_file_id:
		frappe.throw(_("Missing telegram_file_id."))

	dt = _service_request_dt_name(service_request)
	doc = frappe.get_doc(dt, service_request)
	project, site = _assert_service_request_access(link, doc)

	# Ensure Drive folders exist (idempotent).
	try:
		from ferum_custom.api.project_drive import ensure_drive_folders

		ensure_drive_folders(project)
	except Exception:
		frappe.log_error(
			title="Ferum: upload_service_request_attachment ensure_drive_folders",
			message=frappe.get_traceback(),
		)
		raise

	if (
		not site
		or not frappe.db.exists("DocType", _project_site_dt())
		or not frappe.db.exists(_project_site_dt(), site)
	):
		frappe.throw(_("Service Request does not have a valid Project Site."))

	site_folder_url = frappe.db.get_value(_project_site_dt(), site, "drive_folder_url")
	site_folder_id = _drive_folder_id_from_url(site_folder_url)
	if not site_folder_id:
		frappe.throw(_("Drive folder for this object is not configured. Create Drive folders first."))

	token = _telegram_bot_token()
	if not token:
		frappe.throw(_("Telegram bot token is not configured on server."))

	try:
		download_url, suggested_name = _telegram_fetch_file(token=token, file_id=telegram_file_id)
	except requests.RequestException as e:
		# Do not log traceback: it may contain full Telegram API URLs with bot token.
		frappe.log_error(title="Ferum: Telegram getFile failed", message=_safe_requests_error_summary(e))
		raise frappe.ValidationError(
			_("Не удалось получить файл из Telegram. Попробуйте отправить файл ещё раз.")
		) from None
	except Exception as e:
		frappe.log_error(title="Ferum: Telegram getFile failed", message=_safe_requests_error_summary(e))
		raise frappe.ValidationError(_("Не удалось получить файл из Telegram.")) from None

	base_name = telegram_file_name or suggested_name
	base_name = _safe_filename(base_name)
	suffix = os.path.splitext(suggested_name)[1] or os.path.splitext(base_name)[1]

	tmp_path = ""
	try:
		try:
			tmp_path = _download_to_tempfile(download_url, suffix=suffix)
		except requests.RequestException as e:
			# Do not log traceback: it may contain full Telegram API URLs with bot token.
			frappe.log_error(
				title="Ferum: Telegram file download failed", message=_safe_requests_error_summary(e)
			)
			raise frappe.ValidationError(
				_("Не удалось скачать файл из Telegram. Попробуйте отправить файл ещё раз.")
			) from None

		from ferum_custom.integrations.google_drive_folders import (
			ensure_folder,
			get_drive_service,
			upload_file,
		)

		service = get_drive_service()
		requests_root = ensure_folder(service, name="02_ЗАЯВКИ", parent_id=site_folder_id)
		req_folder = ensure_folder(service, name=service_request, parent_id=requests_root.id)
		file_name = base_name if base_name.lower().endswith(suffix.lower()) else f"{base_name}{suffix}"
		drive_file = upload_file(service, local_path=tmp_path, parent_id=req_folder.id, name=file_name)

		try:
			with _as_user("Administrator"):
				req = frappe.get_doc(dt, service_request)
				req.add_comment(
					"Info",
					f"Вложение (бот): {file_name}\n{drive_file.web_view_link or ''}",
				)
		except Exception:
			frappe.log_error(
				title="Ferum: upload_service_request_attachment add_comment", message=frappe.get_traceback()
			)

		return {
			"ok": True,
			"service_request": service_request,
			"project": project,
			"project_site": site,
			"folder_url": req_folder.web_view_link,
			"file_url": drive_file.web_view_link,
			"file_name": file_name,
		}
	finally:
		if tmp_path:
			try:
				os.remove(tmp_path)
			except Exception:
				pass
