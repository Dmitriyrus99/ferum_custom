from __future__ import annotations

import frappe


def execute() -> None:
	# Replace legacy Service Project report shortcuts with standard Project.
	if frappe.db.exists("DocType", "Workspace Shortcut"):
		frappe.db.sql(
			"""
            update `tabWorkspace Shortcut`
            set report_ref_doctype = 'Project'
            where report_ref_doctype = 'Service Project'
            """
		)

	# Hard-hide Service Project in create menu (already expected, keep idempotent).
	if frappe.db.exists("DocType", "Service Project"):
		frappe.db.set_value("DocType", "Service Project", "in_create", 0)
		frappe.db.set_value("DocType", "Service Project", "quick_entry", 0)

	frappe.clear_cache()
