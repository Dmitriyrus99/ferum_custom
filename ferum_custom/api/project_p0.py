from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import nowdate

from ferum_custom.utils.role_resolution import FERUM_DIRECTOR_ROLES, enabled_users_with_roles


def _director_cc_emails() -> list[str]:
	cc: list[str] = []
	for user in enabled_users_with_roles(FERUM_DIRECTOR_ROLES):
		email = frappe.db.get_value("User", user, "email")
		email = str(email or "").strip()
		if email and email not in cc:
			cc.append(email)
	return cc


def _project_official_emails(project_doc) -> list[str]:
	emails: list[str] = []
	for row in project_doc.get("customer_contacts") or []:
		if int(getattr(row, "official_email_verified", 0) or 0) != 1:
			continue
		email = str(getattr(row, "official_email", "") or "").strip()
		if email and email not in emails:
			emails.append(email)
	return emails


def _render_welcome_email(project_doc) -> tuple[str, str]:
	project_name = getattr(project_doc, "project_name", None) or project_doc.name
	pm = getattr(project_doc, "project_manager", None) or ""
	subject = f"Проект {project_name}: приветственное письмо / контакты"

	body = (
		f"Добрый день!\n\n"
		f"Сообщаем, что проект '{project_name}' принят в работу.\n"
		f"Менеджер проекта: {pm}\n\n"
		f"Просим подтвердить контактные данные и предпочтительный канал связи.\n\n"
		f"С уважением,\n"
		f"Ferum\n"
	)
	return subject, body


@frappe.whitelist(methods=["POST"])
def send_welcome_email(project: str) -> dict:
	"""Send a welcome email to verified official customer emails and CC the director."""
	if not project:
		frappe.throw(_("Project is required."))
	project_doc = frappe.get_doc("Project", project)

	# Permissions: allow System Manager, PM roles, or the project's PM.
	roles = set(frappe.get_roles(frappe.session.user))
	is_pm = (getattr(project_doc, "project_manager", None) or "").strip() == frappe.session.user
	pm_roles = {"Project Manager", "Projects Manager"}
	if not ("System Manager" in roles or bool(roles & pm_roles) or is_pm):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	recipients = _project_official_emails(project_doc)
	if not recipients:
		frappe.throw(_("No verified official emails found in Customer Contacts."))

	cc = _director_cc_emails()

	subject, body = _render_welcome_email(project_doc)

	frappe.sendmail(recipients=recipients, cc=cc, subject=subject, message=body)

	project_doc.db_set("welcome_email_sent_date", nowdate(), update_modified=True)
	project_doc.add_comment(
		"Info",
		f"Welcome email sent to {', '.join(recipients)}" + (f" (cc: {', '.join(cc)})" if cc else ""),
	)

	return {"ok": True, "recipients": recipients, "cc": cc}
