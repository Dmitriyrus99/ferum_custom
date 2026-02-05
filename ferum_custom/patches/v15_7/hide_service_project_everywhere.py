from __future__ import annotations

import frappe


def execute() -> None:
	dt = "Service Project"
	if not frappe.db.exists("DocType", dt):
		return

	# Hide doctype name in global search results (best-effort).
	if frappe.db.has_column("DocType", "show_name_in_global_search"):
		frappe.db.set_value("DocType", dt, "show_name_in_global_search", 0)

	if frappe.db.has_column("DocType", "hide_toolbar"):
		frappe.db.set_value("DocType", dt, "hide_toolbar", 1)

	if frappe.db.has_column("DocType", "in_create"):
		frappe.db.set_value("DocType", dt, "in_create", 0)

	if frappe.db.has_column("DocType", "quick_entry"):
		frappe.db.set_value("DocType", dt, "quick_entry", 0)

	# Remove read permissions for all roles except admin/system manager.
	perms = frappe.get_all(
		"DocPerm",
		filters={"parent": dt, "parenttype": "DocType"},
		fields=["name", "role"],
	)
	for p in perms:
		if p.role in {"Administrator", "System Manager"}:
			continue
		frappe.db.set_value(
			"DocPerm",
			p.name,
			{
				"read": 0,
				"create": 0,
				"write": 0,
				"delete": 0,
				"submit": 0,
				"cancel": 0,
				"amend": 0,
				"report": 0,
				"export": 0,
				"print": 0,
			},
		)

	frappe.clear_cache()
