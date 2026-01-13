from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _field_exists(doctype: str, fieldname: str) -> bool:
	return bool(
		frappe.db.get_value(
			"Custom Field",
			{"dt": doctype, "fieldname": fieldname},
			"name",
		)
	) or bool(
		frappe.db.get_value(
			"DocField",
			{"parent": doctype, "parenttype": "DocType", "fieldname": fieldname},
			"name",
		)
	)


def execute() -> None:
	if not frappe.db.exists("DocType", "Project"):
		return

	# Single PM field (required for notifications, escalations and bot UX).
	if not _field_exists("Project", "project_manager"):
		create_custom_fields(
			{
				"Project": [
					{
						"fieldname": "project_manager",
						"label": "Руководитель проекта",
						"fieldtype": "Link",
						"options": "User",
						"insert_after": "ferum_stage",
					}
				]
			},
			ignore_validate=True,
		)

	# Enforce Russian label for UI even if field existed already.
	cf_name = frappe.db.get_value("Custom Field", {"dt": "Project", "fieldname": "project_manager"}, "name")
	if cf_name:
		frappe.db.set_value("Custom Field", cf_name, "label", "Руководитель проекта", update_modified=False)

	frappe.clear_cache()
