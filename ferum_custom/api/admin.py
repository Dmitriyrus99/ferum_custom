from __future__ import annotations

import frappe
from frappe import _


def _has_role(role: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	try:
		return role in set(frappe.get_roles(user))
	except Exception:
		return False


def _require_system_manager() -> None:
	if frappe.session.user == "Guest" or not _has_role("System Manager"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _resolve_user(email_or_name: str) -> str | None:
	value = str(email_or_name or "").strip()
	if not value:
		return None
	if frappe.db.exists("User", value):
		return value
	name = frappe.db.get_value("User", {"email": value}, "name")
	return str(name) if name else None


@frappe.whitelist(methods=["POST"])
def add_user_to_all_projects(*, user: str, dry_run: int | bool = 1) -> dict:
	"""Add a user to every Project.users row (idempotent).

	This is intended for test/staging environments and bot bring-up.
	"""
	_require_system_manager()

	user_name = _resolve_user(user)
	if not user_name:
		frappe.throw(_("User not found: {0}").format(frappe.bold(user)))

	if not frappe.db.exists("DocType", "Project User") or not frappe.db.has_column("Project User", "user"):
		frappe.throw(_("Project User DocType is not installed."), frappe.ValidationError)

	projects = frappe.get_all("Project", pluck="name", limit_page_length=200000)
	if not projects:
		return {"ok": True, "dry_run": bool(int(dry_run)), "user": user_name, "added": 0, "skipped": 0}

	added = 0
	skipped = 0
	to_insert: list[dict[str, object]] = []

	for project in projects:
		project = str(project or "").strip()
		if not project:
			continue
		if frappe.db.exists(
			"Project User",
			{"parenttype": "Project", "parentfield": "users", "parent": project, "user": user_name},
		):
			skipped += 1
			continue
		added += 1
		to_insert.append(
			{
				"doctype": "Project User",
				"parenttype": "Project",
				"parentfield": "users",
				"parent": project,
				"user": user_name,
			}
		)

	if not bool(int(dry_run)) and to_insert:
		for d in to_insert:
			frappe.get_doc(d).insert(ignore_permissions=True)

	return {
		"ok": True,
		"dry_run": bool(int(dry_run)),
		"user": user_name,
		"added": added,
		"skipped": skipped,
	}
