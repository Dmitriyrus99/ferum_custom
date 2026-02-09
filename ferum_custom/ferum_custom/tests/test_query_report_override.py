from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


class TestQueryReportOverride(FrappeTestCase):
	def test_query_report_run_tolerates_empty_filters_for_named_placeholders(self) -> None:
		"""Regression: Query Reports with `%(field)s` placeholders must not 500 on empty filter dicts."""
		from ferum_custom.overrides.query_report import run

		report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": "Ferum Test Placeholder Report",
				"ref_doctype": "Project",
				"module": "Ferum Custom",
				"report_type": "Query Report",
				"query": "select %(project)s as project",
				"filters": [
					{
						"fieldname": "project",
						"label": "Project",
						"fieldtype": "Link",
						"options": "Project",
					}
				],
			}
		).insert(ignore_permissions=True)

		try:
			# UI sends only non-empty filters, so an empty dict is common.
			out = run(report.name, filters="{}", user="Administrator", are_default_filters=True)
			self.assertIsInstance(out, dict)
			self.assertIn("result", out)
		finally:
			frappe.delete_doc("Report", report.name, ignore_permissions=True, force=1)
