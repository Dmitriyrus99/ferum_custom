from __future__ import annotations

import frappe

from ferum_custom.utils.role_resolution import (
	FERUM_DIRECTOR_ROLE,
	FERUM_OFFICE_MANAGER_ROLE,
	FERUM_TENDER_SPECIALIST_ROLE,
)


def _ensure_role(role_name: str) -> None:
	if not role_name or frappe.db.exists("Role", role_name):
		return
	doc = frappe.get_doc({"doctype": "Role", "role_name": role_name})
	doc.insert(ignore_permissions=True)


def _ensure_user(email: str, *, first_name: str, last_name: str) -> str:
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		changed = False
		if not user.enabled:
			user.enabled = 1
			changed = True
		if not (user.first_name or "").strip():
			user.first_name = first_name
			changed = True
		if not (user.last_name or "").strip():
			user.last_name = last_name
			changed = True
		if (user.user_type or "").strip() != "System User":
			user.user_type = "System User"
			changed = True
		if changed:
			user.save(ignore_permissions=True)
		return email

	user = frappe.new_doc("User")
	user.email = email
	user.first_name = first_name
	user.last_name = last_name
	user.enabled = 1
	user.user_type = "System User"
	user.flags.no_welcome_mail = True
	user.insert(ignore_permissions=True)
	return email


def _ensure_user_has_roles(user: str, roles: tuple[str, ...]) -> None:
	try:
		doc = frappe.get_doc("User", user)
		for role in roles:
			if role:
				doc.add_roles(role)
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Ferum P0 user role assignment failed")


def _disable_user(email: str) -> None:
	if not email or not frappe.db.exists("User", email):
		return
	try:
		doc = frappe.get_doc("User", email)
		if doc.enabled:
			doc.enabled = 0
			doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Ferum P0 demo user disable failed")


def execute() -> None:
	"""Replace demo P0 users with real ones and disable demo placeholders.

	The initial patch creates demo users (director@example.com, tender@example.com, office@example.com).
	This patch ensures real Ferum emails exist and have the correct roles, and disables demo users so
	role-based assignment (ToDo/escalations) doesn't target placeholders.
	"""
	# Ensure baseline roles exist.
	for role in (FERUM_DIRECTOR_ROLE, FERUM_TENDER_SPECIALIST_ROLE, FERUM_OFFICE_MANAGER_ROLE):
		_ensure_role(role)

	# Real users.
	director = _ensure_user("rusakov@ferumrus.ru", first_name="Дмитрий", last_name="Русаков")
	tender = _ensure_user("tender@ferumrus.ru", first_name="Тендер", last_name="Специалист")
	office = _ensure_user("client@ferumrus.ru", first_name="Офис", last_name="Менеджер")

	_ensure_user_has_roles(director, (FERUM_DIRECTOR_ROLE,))
	_ensure_user_has_roles(tender, (FERUM_TENDER_SPECIALIST_ROLE,))
	_ensure_user_has_roles(office, (FERUM_OFFICE_MANAGER_ROLE, "Office Manager"))

	# Disable demo placeholder users created by the bootstrap patch.
	for email in ("director@example.com", "tender@example.com", "office@example.com"):
		_disable_user(email)
