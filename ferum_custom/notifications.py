import frappe
import requests
from frappe.utils import cint, get_url_to_form

from ferum_custom.config.settings import get_settings
from ferum_custom.config.types import parse_int

REQUEST_TIMEOUT_SECONDS = 20


def _fastapi_backend_url() -> str | None:
	settings = get_settings()
	return settings.get(
		"FERUM_FASTAPI_BASE_URL",
		"FERUM_FASTAPI_BACKEND_URL",
		"FASTAPI_BACKEND_URL",
		"ferum_fastapi_base_url",
		"ferum_fastapi_backend_url",
	)


def _fastapi_auth_token() -> str | None:
	settings = get_settings()
	return settings.get("FERUM_FASTAPI_AUTH_TOKEN", "FASTAPI_AUTH_TOKEN", "ferum_fastapi_auth_token")


def _default_chat_id() -> int | None:
	settings = get_settings()
	return parse_int(settings.get("FERUM_TELEGRAM_DEFAULT_CHAT_ID", "ferum_telegram_default_chat_id"))


def _get_int_setting(*keys: str) -> int | None:
	settings = get_settings()
	return parse_int(settings.get(*keys))


def _telegram_bot_token() -> str | None:
	settings = get_settings()
	return settings.get("FERUM_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "ferum_telegram_bot_token")


def _telegram_enabled() -> bool:
	# Opt-out at environment level (handy for CI/scripts).
	settings = get_settings()
	disabled = (settings.get("FERUM_DISABLE_TELEGRAM_NOTIFICATIONS") or "").strip().lower()
	if disabled in {"1", "true", "yes", "on"}:
		return False
	try:
		doc = frappe.get_cached_doc("Ferum Custom Settings")
		return cint(getattr(doc, "enable_telegram_notifications", 0) or 0) == 1
	except Exception:
		# Backward-compatible default: enabled if token exists.
		return bool(_telegram_bot_token())


def _send_telegram_direct(chat_id: int, message: str) -> None:
	if not _telegram_enabled():
		return
	token = _telegram_bot_token()
	if not token:
		frappe.log_error(
			title="Telegram Config Error",
			message="Missing FERUM_TELEGRAM_BOT_TOKEN; can't send Telegram message.",
		)
		return

	try:
		resp = requests.post(
			f"https://api.telegram.org/bot{token}/sendMessage",
			json={"chat_id": chat_id, "text": message},
			timeout=REQUEST_TIMEOUT_SECONDS,
		)
		resp.raise_for_status()
	except requests.RequestException as e:
		frappe.log_error(
			title="Telegram Send Error",
			message=f"Telegram sendMessage failed for chat_id {chat_id}: {e}",
		)


def send_telegram_notification_to_fastapi(chat_id: int, message: str) -> None:
	"""Compatibility wrapper: try FastAPI if configured, else send directly via Telegram API."""
	if not _telegram_enabled():
		return
	base_url = _fastapi_backend_url()
	token = _fastapi_auth_token()
	if not base_url or not token:
		_send_telegram_direct(int(chat_id), message)
		return

	headers = {"Authorization": f"Bearer {token}"}
	payload = {"chat_id": int(chat_id), "text": message}
	try:
		response = requests.post(
			f"{base_url}/send_telegram_notification",
			headers=headers,
			json=payload,
			timeout=REQUEST_TIMEOUT_SECONDS,
		)
		response.raise_for_status()
	except requests.RequestException as e:
		frappe.log_error(
			title="Notification Error",
			message=f"FastAPI telegram notification failed for chat_id {chat_id}: {e}",
		)
		# Fallback to direct send so notifications don't silently die.
		_send_telegram_direct(int(chat_id), message)


def _service_object_dt() -> str:
	return "Service Object" if frappe.db.exists("DocType", "Service Object") else "ServiceObject"


def _safe_int_chat_id(raw: str | int | None) -> int | None:
	if raw is None:
		return None
	try:
		return int(str(raw).strip())
	except Exception:
		return None


def _chat_ids_for_users(users: set[str]) -> set[int]:
	users = {u for u in users if u}
	if not users or not frappe.db.exists("DocType", "Telegram User Link"):
		return set()
	rows = frappe.get_all(
		"Telegram User Link",
		filters={"user": ["in", list(users)]},
		fields=["chat_id"],
		limit=500,
	)
	out: set[int] = set()
	for r in rows:
		cid = _safe_int_chat_id(r.get("chat_id"))
		if cid is not None:
			out.add(cid)
	return out


def _chat_ids_for_project_subscribers(project: str) -> set[int]:
	return _chat_ids_for_project_subscribers_typed(project, parenttype="Service Project")


def _chat_ids_for_project_subscribers_typed(project: str, *, parenttype: str) -> set[int]:
	if not project:
		return set()
	if not frappe.db.exists("DocType", "Project Telegram User Item") or not frappe.db.exists(
		"DocType", "Telegram User Link"
	):
		return set()
	link_names = frappe.get_all(
		"Project Telegram User Item",
		filters={"parenttype": parenttype, "parent": project},
		pluck="telegram_user",
		limit=500,
	)
	link_names = [n for n in link_names if n]
	if not link_names:
		return set()
	rows = frappe.get_all(
		"Telegram User Link",
		filters={"name": ["in", link_names]},
		fields=["chat_id"],
		limit=500,
	)
	out: set[int] = set()
	for r in rows:
		cid = _safe_int_chat_id(r.get("chat_id"))
		if cid is not None:
			out.add(cid)
	return out


def _service_request_context(doc) -> dict:
	"""Best-effort context resolver for Service Request notifications."""
	# New model: ERPNext Project + Project Site
	project = getattr(doc, "erp_project", None) or None
	project_type = "Project" if project else "Service Project"

	project_site = getattr(doc, "project_site", None)
	object_name = None
	address = None
	site_engineer = None
	if (
		project_site
		and frappe.db.exists("DocType", "Project Site")
		and frappe.db.exists("Project Site", project_site)
	):
		object_name, address, site_engineer, project_from_site = frappe.db.get_value(
			"Project Site",
			project_site,
			["site_name", "address", "default_engineer", "parent"],
		)
		project = project or project_from_site
		project_type = "Project"

	# Legacy fallback: Service Object / Service Project
	so_dt = _service_object_dt()
	service_object = getattr(doc, "service_object", None)
	so_engineer = None
	if not project and service_object and frappe.db.exists(so_dt, service_object):
		object_name, address, project, so_engineer = frappe.db.get_value(
			so_dt,
			service_object,
			["object_name", "address", "project", "default_engineer"],
		)
		project_type = "Service Project"

	pm = None
	customer = getattr(doc, "customer", None)
	if project_type == "Project" and project and frappe.db.exists("Project", project):
		project_meta = frappe.get_meta("Project")
		project_customer = None
		if project_meta.has_field("project_manager"):
			pm = frappe.db.get_value("Project", project, "project_manager")
		if project_meta.has_field("customer"):
			project_customer = frappe.db.get_value("Project", project, "customer")
		customer = customer or project_customer
	elif project_type == "Service Project" and project and frappe.db.exists("Service Project", project):
		pm, project_engineer, project_customer = frappe.db.get_value(
			"Service Project",
			project,
			["project_manager", "default_engineer", "customer"],
		)
		customer = customer or project_customer
		if not site_engineer:
			site_engineer = project_engineer

	assigned_to = getattr(doc, "assigned_to", None) or site_engineer or so_engineer
	project_name = None
	if project_type == "Project" and project and frappe.db.exists("Project", project):
		project_meta = frappe.get_meta("Project")
		if project_meta.has_field("project_name"):
			project_name = frappe.db.get_value("Project", project, "project_name")
	return {
		"service_object": service_object,
		"object_name": object_name,
		"address": address,
		"project": project,
		"project_name": project_name,
		"project_type": project_type,
		"project_manager": pm,
		"assigned_to": assigned_to,
		"customer": customer,
	}


def _notify_chat_ids(chat_ids: set[int], message: str) -> None:
	for cid in sorted(chat_ids):
		try:
			send_telegram_notification_to_fastapi(cid, message)
		except Exception:
			frappe.log_error(
				title="Telegram Notification Error",
				message=f"Failed to send telegram notification to chat_id={cid}",
			)


def notify_new_service_request(doc, method):
	if not _telegram_enabled():
		return
	try:
		ctx = _service_request_context(doc)
		url = get_url_to_form(doc.doctype, doc.name)
		title = (getattr(doc, "title", "") or "").strip()
		status = getattr(doc, "status", None)
		priority = getattr(doc, "priority", None)
		project = str(ctx.get("project") or "")
		project_name = (str(ctx.get("project_name") or "")).strip()
		project_label = f"{project} — {project_name}" if project_name and project_name != project else project
		obj = ctx.get("object_name") or ctx.get("service_object") or ""
		address = (str(ctx.get("address") or "")).strip()
		created_by = getattr(doc, "owner", None) or ""

		lines = [
			f"🆕 Новая заявка: {doc.name}",
			f"Проект: {project_label}",
			f"Объект: {obj}",
		]
		if address:
			lines.append(f"Адрес: {address}")
		lines.extend(
			[
				f"Приоритет: {priority}",
				f"Статус: {status}",
				f"Создал: {created_by}",
				title,
				url,
			]
		)
		msg = "\n".join([l for l in lines if l])

		recipients: set[str] = set()
		if ctx.get("assigned_to"):
			recipients.add(str(ctx["assigned_to"]))
		if ctx.get("project_manager"):
			recipients.add(str(ctx["project_manager"]))
		if getattr(doc, "owner", None):
			recipients.add(str(doc.owner))

		chat_ids = _chat_ids_for_users(recipients)
		project_type = ctx.get("project_type") or "Service Project"
		chat_ids |= _chat_ids_for_project_subscribers_typed(str(project), parenttype=str(project_type))
		if _default_chat_id():
			chat_ids.add(int(_default_chat_id() or 0))
		_notify_chat_ids(chat_ids, msg)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "notify_new_service_request failed")


def notify_service_request_status_change(doc, method):
	if not _telegram_enabled():
		return
	try:
		before = None
		try:
			before = doc.get_doc_before_save()
		except Exception:
			before = None
		if not before:
			return

		changes: list[str] = []
		if getattr(before, "status", None) != getattr(doc, "status", None):
			changes.append(f"Статус: {getattr(before, 'status', None)} → {getattr(doc, 'status', None)}")
		if getattr(before, "assigned_to", None) != getattr(doc, "assigned_to", None):
			changes.append(
				f"Назначено: {getattr(before, 'assigned_to', None)} → {getattr(doc, 'assigned_to', None)}"
			)
		if getattr(before, "priority", None) != getattr(doc, "priority", None):
			changes.append(
				f"Приоритет: {getattr(before, 'priority', None)} → {getattr(doc, 'priority', None)}"
			)
		if not changes:
			return

		ctx = _service_request_context(doc)
		url = get_url_to_form(doc.doctype, doc.name)
		project = str(ctx.get("project") or "")
		project_name = (str(ctx.get("project_name") or "")).strip()
		project_label = f"{project} — {project_name}" if project_name and project_name != project else project
		obj = ctx.get("object_name") or ctx.get("service_object") or ""
		address = (str(ctx.get("address") or "")).strip()
		lines = [
			f"🔔 Обновление заявки: {doc.name}",
			f"Проект: {project_label}",
			f"Объект: {obj}",
		]
		if address:
			lines.append(f"Адрес: {address}")
		lines.extend(changes)
		lines.append(url)
		msg = "\n".join([l for l in lines if l])

		recipients: set[str] = set()
		if ctx.get("assigned_to"):
			recipients.add(str(ctx["assigned_to"]))
		if ctx.get("project_manager"):
			recipients.add(str(ctx["project_manager"]))
		if getattr(doc, "owner", None):
			recipients.add(str(doc.owner))

		chat_ids = _chat_ids_for_users(recipients)
		project_type = ctx.get("project_type") or "Service Project"
		chat_ids |= _chat_ids_for_project_subscribers_typed(str(project), parenttype=str(project_type))
		if _default_chat_id():
			chat_ids.add(int(_default_chat_id() or 0))
		_notify_chat_ids(chat_ids, msg)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "notify_service_request_status_change failed")


def notify_new_service_report(doc, method):
	# Notify relevant parties (e.g., Project Manager, Admin) about a new Service Report
	message = f"New Service Report created: {doc.name} for Service Request {doc.service_request}. Status: {doc.status}."

	# Example: Send to a specific Telegram chat ID
	chat_id = (
		_get_int_setting("ferum_telegram_pm_admin_chat_id", "FERUM_TELEGRAM_PM_ADMIN_CHAT_ID")
		or _default_chat_id()
	)
	if chat_id:
		send_telegram_notification_to_fastapi(chat_id, message)

	# Example: Send email notification
	# frappe.sendmail(
	#     recipients=["pm@example.com", "admin@example.com"],
	#     subject=f"New Service Report: {doc.name}",
	#     content=message
	# )


def notify_service_report_status_change(doc, method):
	# Notify relevant parties about Service Report status change (e.g., Submitted, Approved)
	message = f"Service Report {doc.name} status changed to {doc.status}. For Service Request {doc.service_request}."

	# Example: Send to a specific Telegram chat ID
	chat_id = (
		_get_int_setting("ferum_telegram_pm_admin_chat_id", "FERUM_TELEGRAM_PM_ADMIN_CHAT_ID")
		or _default_chat_id()
	)
	if chat_id:
		send_telegram_notification_to_fastapi(chat_id, message)

	# Example: Send email notification
	# frappe.sendmail(
	#     recipients=["pm@example.com", "admin@example.com"],
	#     subject=f"Service Report {doc.name} Status Update",
	#     content=message
	# )


def notify_new_invoice(doc, method):
	# Notify relevant parties (e.g., Accountant, Admin) about a new Invoice
	message = f"New Invoice created: {doc.name} for {doc.counterparty_name}. Amount: {doc.amount}. Status: {doc.status}."

	# Example: Send to a specific Telegram chat ID
	chat_id = (
		_get_int_setting("ferum_telegram_accountant_chat_id", "FERUM_TELEGRAM_ACCOUNTANT_CHAT_ID")
		or _default_chat_id()
	)
	if chat_id:
		send_telegram_notification_to_fastapi(chat_id, message)

	# Example: Send email notification
	# frappe.sendmail(
	#     recipients=["accountant@example.com", "admin@example.com"],
	#     subject=f"New Invoice: {doc.name}",
	#     content=message
	# )


def notify_invoice_status_change(doc, method):
	# Notify relevant parties about Invoice status change (e.g., Paid, Overdue)
	message = f"Invoice {doc.name} status changed to {doc.status}. For {doc.counterparty_name}. Amount: {doc.amount}."

	# Example: Send to a specific Telegram chat ID
	chat_id = (
		_get_int_setting("ferum_telegram_accountant_chat_id", "FERUM_TELEGRAM_ACCOUNTANT_CHAT_ID")
		or _default_chat_id()
	)
	if chat_id:
		send_telegram_notification_to_fastapi(chat_id, message)

	# Example: Send email notification
	# frappe.sendmail(
	#     recipients=["accountant@example.com", "admin@example.com"],
	#     subject=f"Invoice {doc.name} Status Update",
	#     content=message
	# )
