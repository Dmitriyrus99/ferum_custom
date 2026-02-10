from __future__ import annotations

import frappe

TRUTH_DT = "Project Site"
LEGACY_ROW_DT = "Project Site Row"


def _is_table_doctype(dt: str) -> bool:
	try:
		row = frappe.db.get_value("DocType", dt, ["istable"], as_dict=True) or {}
		return int(row.get("istable") or 0) == 1
	except Exception:
		return False


def truth_doctype() -> str:
	"""Canonical Project Site doctype (truth model)."""
	return TRUTH_DT


def legacy_row_doctype() -> str | None:
	"""Legacy child-table doctype used by Project.project_sites.

	Compatibility:
	- New model: `Project Site Row`
	- Old model: `Project Site` (when it was istable=1)
	"""
	if frappe.db.exists("DocType", LEGACY_ROW_DT):
		return LEGACY_ROW_DT
	if frappe.db.exists("DocType", TRUTH_DT) and _is_table_doctype(TRUTH_DT):
		return TRUTH_DT
	return None


def is_truth_enabled() -> bool:
	return frappe.db.exists("DocType", TRUTH_DT) and not _is_table_doctype(TRUTH_DT)


def site_belongs_to_project(*, site: str, project: str) -> bool:
	site = str(site or "").strip()
	project = str(project or "").strip()
	if not site or not project:
		return False

	# Prefer truth doctype if it has an explicit `project` field.
	if frappe.db.exists("DocType", TRUTH_DT) and frappe.db.has_column(TRUTH_DT, "project"):
		val = frappe.db.get_value(TRUTH_DT, site, "project")
		if str(val or "").strip() == project:
			return True

	# Fallback to legacy child row parent.
	row_dt = legacy_row_doctype()
	if row_dt and frappe.db.has_column(row_dt, "parent"):
		val = frappe.db.get_value(row_dt, site, "parent")
		if str(val or "").strip() == project:
			return True

	return False


def list_sites_for_project(
	*,
	project: str,
	engineer: str | None = None,
	limit: int = 500,
	order_by: str = "modified desc",
) -> list[dict]:
	"""List Project Sites for a Project.

	Returns normalized dicts:
	- name
	- site_name
	- address
	- default_engineer
	- drive_folder_url
	"""
	project = str(project or "").strip()
	engineer = str(engineer or "").strip() or None
	if not project:
		return []

	filters_truth: dict[str, object] = {"project": project}
	if engineer and frappe.db.has_column(TRUTH_DT, "default_engineer"):
		filters_truth["default_engineer"] = engineer

	if is_truth_enabled() and frappe.db.has_column(TRUTH_DT, "project"):
		rows = frappe.get_all(
			TRUTH_DT,
			filters=filters_truth,
			fields=[
				"name",
				"site_name",
				"address",
				"default_engineer",
				"drive_folder_url",
				"modified",
			],
			limit=min(int(limit or 500), 1000),
			order_by=order_by,
		)
		if rows:
			return rows

	# Fallback: legacy child rows.
	row_dt = legacy_row_doctype()
	if not row_dt:
		return []

	filters_row: dict[str, object] = {
		"parenttype": "Project",
		"parent": project,
		"parentfield": "project_sites",
	}
	if engineer and frappe.db.has_column(row_dt, "default_engineer"):
		filters_row["default_engineer"] = engineer

	return frappe.get_all(
		row_dt,
		filters=filters_row,
		fields=[
			"name",
			"site_name",
			"address",
			"default_engineer",
			"drive_folder_url",
			"modified",
		],
		limit=min(int(limit or 500), 1000),
		order_by="idx asc" if frappe.db.has_column(row_dt, "idx") else order_by,
	)
