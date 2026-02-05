from __future__ import annotations

import frappe


def execute() -> None:
	"""Register Script Report implemented in app code: `Project Sites`."""
	report_name = "Project Sites"

	if frappe.db.exists("Report", report_name):
		report = frappe.get_doc("Report", report_name)
	else:
		report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": report_name,
				"module": "Ferum Custom",
				"ref_doctype": "Project",
			}
		)

	report.module = "Ferum Custom"
	report.ref_doctype = "Project"
	report.report_type = "Script Report"
	report.is_standard = "Yes"
	report.disabled = 0
	report.query = ""
	report.report_script = ""

	if report.is_new():
		report.insert(ignore_permissions=True)
	else:
		report.save(ignore_permissions=True)

	frappe.clear_cache()
