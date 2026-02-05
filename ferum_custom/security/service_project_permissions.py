from __future__ import annotations

import frappe


def service_project_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	"""Disable legacy ServiceProject mutations while keeping read for history."""
	user = user or frappe.session.user
	if not user or user == "Administrator":
		return None

	# Portal clients must not access legacy financial/operational structures.
	if "Client" in frappe.get_roles(user):
		return False

	# Hide legacy Service Project from Desk UI for non-admin users.
	if ptype in {None, "read", "report", "export", "print"}:
		return False

	# Disallow creating/editing/deleting legacy projects for all non-admin users.
	if ptype in {"create", "write", "delete", "submit", "cancel", "amend"}:
		return False

	return None
