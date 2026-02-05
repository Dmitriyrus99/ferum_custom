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


def _ensure_user_has_role(user: str, role_name: str) -> None:
	try:
		doc = frappe.get_doc("User", user)
		doc.add_roles(role_name)
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Ferum P0 role assignment failed")


def execute() -> None:
	"""Create baseline Ferum P0 roles and demo users.

	These roles are used by P0 automations (ToDos, escalations, welcome email CC).
	Users are created only if they do not exist yet.
	"""
	for role in (FERUM_DIRECTOR_ROLE, FERUM_TENDER_SPECIALIST_ROLE, FERUM_OFFICE_MANAGER_ROLE):
		_ensure_role(role)

	# Baseline users (can be replaced by real emails later).
	director_user = _ensure_user("director@example.com", first_name="General", last_name="Director")
	tender_user = _ensure_user("tender@example.com", first_name="Tender", last_name="Specialist")
	office_user = _ensure_user("office@example.com", first_name="Office", last_name="Manager")

	_ensure_user_has_role(director_user, FERUM_DIRECTOR_ROLE)
	_ensure_user_has_role(tender_user, FERUM_TENDER_SPECIALIST_ROLE)
	_ensure_user_has_role(office_user, FERUM_OFFICE_MANAGER_ROLE)
