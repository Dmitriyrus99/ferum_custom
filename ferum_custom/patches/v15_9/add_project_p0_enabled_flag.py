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

	# Soft rollout: gates apply only when this flag is enabled.
	if not _field_exists("Project", "ferum_p0_enabled"):
		create_custom_fields(
			{
				"Project": [
					{
						"fieldname": "ferum_p0_enabled",
						"label": "Процесс P0 активен",
						"fieldtype": "Check",
						"default": 1,
						"insert_after": "ferum_stage",
					}
				]
			},
			ignore_validate=True,
		)

	# Enforce Russian label even if field existed already.
	cf_name = frappe.db.get_value("Custom Field", {"dt": "Project", "fieldname": "ferum_p0_enabled"}, "name")
	if cf_name:
		frappe.db.set_value("Custom Field", cf_name, "label", "Процесс P0 активен", update_modified=False)

	frappe.clear_cache()
