from __future__ import annotations

import frappe

LEGACY_DT = "Project Site Row"
TRUTH_DT = "Project Site"


def execute() -> None:
	"""Repair truth `Project Site` names to match legacy child-row names.

	Historical context:
	- Legacy project objects were stored as child rows (`Project Site` istable=1, now `Project Site Row`).
	- Service Request.project_site historically linked to those child-row `name` values.
	- The truth DocType `Project Site` uses a naming series, so earlier migrations could create rows as
	  PS-00001 with `legacy_key=project_site_row:<row_name>`, breaking link integrity.

	This patch is idempotent and safe to rerun.
	"""
	if not frappe.db.exists("DocType", LEGACY_DT):
		return
	if not frappe.db.exists("DocType", TRUTH_DT):
		return

	istable = frappe.db.get_value("DocType", TRUTH_DT, "istable") or 0
	if int(istable or 0) == 1:
		# Truth doctype is not installed / still legacy. Nothing to repair.
		return

	row_names = frappe.get_all(
		LEGACY_DT,
		filters={"parenttype": "Project", "parentfield": "project_sites"},
		pluck="name",
		limit_page_length=200000,
	)
	if not row_names:
		return

	renamed = 0
	for row_name in row_names:
		row_name = str(row_name or "").strip()
		if not row_name:
			continue
		if frappe.db.exists(TRUTH_DT, row_name):
			continue

		legacy_key = f"project_site_row:{row_name}"
		existing = frappe.db.get_value(TRUTH_DT, {"legacy_key": legacy_key}, "name")
		existing = str(existing or "").strip() or None
		if not existing or existing == row_name:
			continue

		try:
			frappe.rename_doc(TRUTH_DT, existing, row_name, force=True, ignore_permissions=True)
			renamed += 1
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				"Repair Project Site truth name failed",
			)

	frappe.db.commit()
	frappe.clear_cache()

	if renamed:
		frappe.log_error(title="Ferum: repair_project_site_truth_names", message=f"renamed={renamed}")
