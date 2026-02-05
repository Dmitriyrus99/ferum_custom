from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _field_exists(doctype: str, fieldname: str) -> bool:
	return bool(frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")) or bool(
		frappe.db.get_value(
			"DocField",
			{"parent": doctype, "parenttype": "DocType", "fieldname": fieldname},
			"name",
		)
	)


def execute() -> None:
	if not frappe.db.exists("DocType", "Project") or not frappe.db.exists(
		"DocType", "Project Telegram User Item"
	):
		return

	if _field_exists("Project", "telegram_users"):
		return

	custom_fields = [
		{
			"fieldname": "telegram_section",
			"label": "Telegram",
			"fieldtype": "Section Break",
			"insert_after": "project_sites",
		},
		{
			"fieldname": "telegram_users",
			"label": "Telegram Subscribers",
			"fieldtype": "Table",
			"options": "Project Telegram User Item",
			"insert_after": "telegram_section",
		},
	]

	create_custom_fields({"Project": custom_fields}, ignore_validate=True)
	frappe.clear_cache()
