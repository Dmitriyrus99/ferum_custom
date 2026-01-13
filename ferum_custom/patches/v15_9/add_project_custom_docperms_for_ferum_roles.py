from __future__ import annotations

import frappe


def _upsert_custom_docperm(parent: str, role: str, permlevel: int, values: dict) -> None:
	existing = frappe.db.get_value(
		"Custom DocPerm",
		{"parent": parent, "role": role, "permlevel": int(permlevel)},
		"name",
	)
	if existing:
		frappe.db.set_value("Custom DocPerm", existing, values, update_modified=False)
		return

	doc = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": parent,
			"role": role,
			"permlevel": int(permlevel),
			**values,
		}
	)
	doc.insert(ignore_permissions=True)


def execute() -> None:
	"""Grant Ferum operational roles access to ERPNext Project.

	ERPNext `Project` ships with permissions for `Projects Manager/Projects User`, while Ferum uses
	`Project Manager/Office Manager/Service Engineer/...`. Without custom permissions, these users
	cannot open Project to complete P0 steps.
	"""
	if not frappe.db.exists("DocType", "Custom DocPerm"):
		return
	if not frappe.db.exists("DocType", "Project"):
		return

	role_perms: dict[str, dict] = {
		# Ferum roles
		"Ferum Tender Specialist": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "email": 1},
		"Ferum Office Manager": {"read": 1, "write": 1, "create": 0, "delete": 0, "report": 1},
		"Ferum Director": {"read": 1, "write": 1, "create": 0, "delete": 0, "report": 1, "email": 1},
		# Existing Ferum operational roles / profiles
		"Project Manager": {"read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "email": 1},
		"Office Manager": {"read": 1, "write": 1, "create": 0, "delete": 0, "report": 1},
		"Service Engineer": {"read": 1, "write": 0, "create": 0, "delete": 0, "report": 1},
		"General Director": {"read": 1, "write": 1, "create": 0, "delete": 0, "report": 1, "email": 1},
	}

	for role, perms in role_perms.items():
		if not frappe.db.exists("Role", role):
			continue
		_upsert_custom_docperm("Project", role, 0, perms)

	frappe.clear_cache()

