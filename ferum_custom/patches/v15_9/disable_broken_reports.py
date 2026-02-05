from __future__ import annotations

import frappe


def execute() -> None:
	"""Disable Report records that point to missing python modules.

	These records cause 500s when opened. We disable them instead of deleting to keep history.
	"""

	report_names: tuple[str, ...] = (
		"SLA Breaches",
		"Upcoming Maintenance Tasks",
		"SLA Summary by Priority",
	)

	for name in report_names:
		if frappe.db.exists("Report", name):
			frappe.db.set_value("Report", name, "disabled", 1, update_modified=False)

	frappe.clear_cache()
