from __future__ import annotations

import frappe


def _convert(report_name: str, *, ref_doctype: str) -> None:
	if frappe.db.exists("Report", report_name):
		report = frappe.get_doc("Report", report_name)
	else:
		report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": report_name,
				"module": "Ferum Custom",
				"ref_doctype": ref_doctype,
			}
		)

	report.module = "Ferum Custom"
	report.ref_doctype = ref_doctype
	report.report_type = "Script Report"
	report.is_standard = "Yes"
	report.disabled = 0
	report.query = ""
	report.report_script = ""

	if report.is_new():
		report.insert(ignore_permissions=True)
	else:
		report.save(ignore_permissions=True)


def execute() -> None:
	"""Fix Query Reports that crash when filters are missing.

	Frappe's Query Report parameter interpolation requires keys to exist in the mapping.
	When the UI/API calls the report with empty filters `{}`, it raises:
	`TypeError: format requires a mapping`.

	We convert the affected reports to Script Reports implemented in the app code.
	"""
	_convert("Invoices by Project", ref_doctype="Invoice")
	_convert("Service Requests by Project", ref_doctype="Service Request")

