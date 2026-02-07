from __future__ import annotations

import frappe


def _resolve_user(email_or_name: str) -> str | None:
	value = str(email_or_name or "").strip()
	if not value:
		return None
	if frappe.db.exists("User", value):
		return value
	user = frappe.db.get_value("User", {"email": value}, "name")
	return str(user) if user else None


def add_user_to_all_projects(email_or_name: str) -> int:
	"""Add user to Project.users for all existing projects (idempotent).

	Important: inserts `Project User` child rows directly to avoid triggering Project validations.
	"""
	user = _resolve_user(email_or_name)
	if not user:
		return 0

	if not frappe.db.exists("DocType", "Project") or not frappe.db.exists("DocType", "Project User"):
		return 0

	project_meta = frappe.get_meta("Project")
	if not project_meta.has_field("users"):
		return 0

	if not frappe.db.has_column("Project User", "user"):
		return 0

	added = 0
	projects = frappe.get_all("Project", pluck="name")
	for project in projects:
		project = str(project or "").strip()
		if not project:
			continue
		if frappe.db.exists(
			"Project User", {"parenttype": "Project", "parent": project, "parentfield": "users", "user": user}
		):
			continue

		row = frappe.get_doc(
			{
				"doctype": "Project User",
				"parenttype": "Project",
				"parent": project,
				"parentfield": "users",
				"user": user,
			}
		)
		row.insert(ignore_permissions=True)
		added += 1

	return added
