from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
	if not frappe.db.exists("DocType", "Ferum Custom Settings"):
		return

	create_custom_fields(
		{
			"Ferum Custom Settings": [
				{
					"fieldname": "project_p0_section",
					"label": "Project P0",
					"fieldtype": "Section Break",
					"insert_after": "telegram_bot_section",
				},
				{
					"fieldname": "director_user",
					"label": "Director User",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "project_p0_section",
				},
				{
					"fieldname": "tender_specialist_user",
					"label": "Tender Specialist User",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "director_user",
				},
				{
					"fieldname": "office_manager_user",
					"label": "Office Manager User",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "tender_specialist_user",
				},
			]
		},
		ignore_validate=True,
	)
	frappe.clear_cache()
