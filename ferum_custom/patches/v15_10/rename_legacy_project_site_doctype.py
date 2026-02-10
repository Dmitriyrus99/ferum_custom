from __future__ import annotations

import frappe


def _is_table_doctype(name: str) -> bool:
	try:
		dt = frappe.get_doc("DocType", name)
		return int(getattr(dt, "istable", 0) or 0) == 1
	except Exception:
		return False


def _update_project_sites_custom_field(*, new_child_dt: str) -> None:
	"""Ensure Project.project_sites (Table) points to the legacy child doctype."""
	if not frappe.db.exists("DocType", "Custom Field"):
		return
	cf_name = frappe.db.get_value(
		"Custom Field",
		{"dt": "Project", "fieldname": "project_sites"},
		"name",
	)
	if not cf_name:
		return
	try:
		cf = frappe.get_doc("Custom Field", cf_name)
	except Exception:
		return
	if getattr(cf, "fieldtype", None) != "Table":
		return
	if getattr(cf, "options", None) == new_child_dt:
		return
	cf.options = new_child_dt
	cf.save(ignore_permissions=True)


def execute() -> None:
	"""Rename legacy child DocType `Project Site` -> `Project Site Row`.

	This patch is **pre_model_sync** because it must run before doctype sync:
	- frees up the name `Project Site` for the new truth doctype
	- keeps Project.project_sites pointing to a child doctype
	"""
	old = "Project Site"
	new = "Project Site Row"

	if not frappe.db.exists("DocType", old):
		return
	if frappe.db.exists("DocType", new):
		# Already renamed (or created by previous runs) -> just ensure Project field points to it.
		_update_project_sites_custom_field(new_child_dt=new)
		frappe.clear_cache()
		return

	# Only rename if it's the legacy child table.
	if not _is_table_doctype(old):
		return

	frappe.rename_doc("DocType", old, new, force=True)

	# Ensure the Project field points to the child doctype name.
	_update_project_sites_custom_field(new_child_dt=new)

	frappe.clear_cache()
