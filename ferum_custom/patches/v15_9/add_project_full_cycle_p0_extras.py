from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
	if not frappe.db.exists("DocType", "Project"):
		return

	# These fields are referenced by P0 gate validations.
	create_custom_fields(
		{
			"Project": [
				{
					"fieldname": "legal_review_director_override",
					"label": "Legal Review Director Override",
					"fieldtype": "Check",
					"insert_after": "legal_review_status",
				},
				{
					"fieldname": "director_approved_execution_mode",
					"label": "Director Approved Execution Mode",
					"fieldtype": "Check",
					"insert_after": "execution_mode",
				},
				{
					"fieldname": "photo_only_confirmed",
					"label": "Photo-only Confirmed (PM)",
					"fieldtype": "Check",
					"insert_after": "photo_survey_format",
				},
			]
		},
		ignore_validate=True,
	)
	frappe.clear_cache()
