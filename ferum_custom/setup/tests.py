from __future__ import annotations

import frappe


def before_tests() -> None:
	if not getattr(frappe.flags, "in_test", False):
		return

	ensure_erpnext_test_cost_centers()


def ensure_erpnext_test_cost_centers(company: str = "_Test Company") -> None:
	"""Ensure ERPNext standard test Cost Centers exist.

	`bench run-tests --app ferum_custom` executes only this app's `before_tests` hook,
	so we need a minimal set of ERPNext test records to exist for linked doctypes
	used during test record generation (e.g. Brand defaults).
	"""

	if not frappe.db.exists("Company", company):
		return

	company_abbr = frappe.db.get_value("Company", company, "abbr") or "_TC"
	parent_cost_center = f"{company} - {company_abbr}"
	did_change = False

	if not frappe.db.exists("Cost Center", parent_cost_center):
		root = frappe.get_doc(
			{
				"doctype": "Cost Center",
				"company": company,
				"cost_center_name": company,
				"is_group": 1,
				"parent_cost_center": None,
			}
		)
		root.flags.ignore_permissions = True
		root.flags.ignore_mandatory = True
		root.insert(ignore_if_duplicate=True)
		did_change = True

	for cost_center_name in (
		"_Test Cost Center",
		"_Test Cost Center 2",
		"_Test Write Off Cost Center",
	):
		expected_name = f"{cost_center_name} - {company_abbr}"
		if frappe.db.exists("Cost Center", expected_name):
			continue

		cc = frappe.get_doc(
			{
				"doctype": "Cost Center",
				"company": company,
				"cost_center_name": cost_center_name,
				"is_group": 0,
				"parent_cost_center": parent_cost_center,
			}
		)
		cc.flags.ignore_permissions = True
		cc.insert(ignore_if_duplicate=True)
		did_change = True

	if did_change:
		frappe.db.commit()
