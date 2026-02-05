from __future__ import annotations

import frappe
from frappe.utils import nowdate

from ferum_custom.notifications import send_telegram_notification_to_fastapi
from ferum_custom.utils.role_resolution import FERUM_DIRECTOR_ROLES, enabled_users_with_roles

from .project_full_cycle import _stage_index, maybe_trigger_customer_ignored_mail_task


def _resolve_chat_ids_for_users(users: set[str]) -> set[int]:
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
		try:
			out.add(int(str(r.get("chat_id") or "").strip()))
		except Exception:
			continue
	return out


def _notify_users(users: set[str], subject: str, body: str) -> None:
	users = {u for u in users if u}
	if not users:
		return

	emails = []
	for u in users:
		email = frappe.db.get_value("User", u, "email")
		if email:
			emails.append(email)

	if emails:
		try:
			frappe.sendmail(recipients=emails, subject=subject, message=body)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Project P0 escalation email failed")

	for cid in _resolve_chat_ids_for_users(users):
		try:
			send_telegram_notification_to_fastapi(cid, f"{subject}\n{body}")
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Project P0 escalation telegram failed")


def _director_users() -> set[str]:
	users = set(enabled_users_with_roles(FERUM_DIRECTOR_ROLES))
	return users or {"Administrator"}


def run_daily_project_escalations() -> None:
	"""Daily scheduler job for P0 deadlines/escalations."""
	if not frappe.db.exists("DocType", "Project") or not frappe.get_meta("Project").has_field("ferum_stage"):
		return

	today = nowdate()
	project_meta = frappe.get_meta("Project")
	filters: dict = {}
	if project_meta.has_field("ferum_p0_enabled"):
		filters["ferum_p0_enabled"] = 1
	fields = ["name", "ferum_stage"]
	if project_meta.has_field("project_name"):
		fields.insert(1, "project_name")
	if project_meta.has_field("project_manager"):
		fields.insert(2, "project_manager")
	fields.extend(
		[
			"contractor_selected_deadline",
			"photo_survey_deadline",
			"sent_to_customer_date",
			"if_customer_ignored_trigger_mail_task",
		]
	)
	rows = frappe.get_all(
		"Project",
		filters=filters,
		fields=fields,
		limit=2000,
	)

	director_users = _director_users()

	for r in rows:
		name = r.get("name")
		stage = r.get("ferum_stage")
		pm = (r.get("project_manager") or "").strip()
		recipients = set(director_users)
		if pm:
			recipients.add(pm)

		# Deadline 1: contractor selected/contracted
		deadline = r.get("contractor_selected_deadline")
		if (
			deadline
			and today >= deadline
			and _stage_index(stage) < _stage_index("Contractor Selected/Contracted")
		):
			subject = f"[P0] Просрочен дедлайн подрядчика: Project {name}"
			body = (
				f"Проект: {name}\n"
				f"Стадия: {stage}\n"
				f"Дедлайн 'Contractor Selected/Contracted': {deadline}\n"
				"Требуется эскалация: выбрать подрядчика/сценарий исполнения и пройти гейты стадии."
			)
			_notify_users(recipients, subject, body)

		# Deadline 2: primary survey completed
		survey_deadline = r.get("photo_survey_deadline")
		if (
			survey_deadline
			and today >= survey_deadline
			and _stage_index(stage) < _stage_index("Primary Survey Completed")
		):
			subject = f"[P0] Просрочен дедлайн первички: Project {name}"
			body = (
				f"Проект: {name}\n"
				f"Стадия: {stage}\n"
				f"Дедлайн 'Primary Survey Completed': {survey_deadline}\n"
				"Требуется эскалация: первичное обследование/фото/чек-лист."
			)
			_notify_users(recipients, subject, body)

		# Customer ignored act/defects: create mail task after 7 days.
		try:
			doc = frappe.get_doc("Project", name)
			maybe_trigger_customer_ignored_mail_task(doc)
			if (
				int(getattr(doc, "if_customer_ignored_trigger_mail_task", 0) or 0) == 1
				and int(r.get("if_customer_ignored_trigger_mail_task") or 0) == 0
			):
				doc.save(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Project P0 ignored mail task failed")
