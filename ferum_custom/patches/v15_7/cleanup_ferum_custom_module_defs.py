from __future__ import annotations

import frappe


def _get_modules_in_use() -> set[str]:
	modules: set[str] = set()

	# DocTypes belonging to the app
	if frappe.db.table_exists("DocType") and frappe.db.has_column("DocType", "module"):
		modules.update(
			frappe.get_all(
				"DocType",
				filters={"app": "ferum_custom"},
				pluck="module",
				limit_page_length=0,
			)
		)

	# Common desk artifacts that store module
	for dt in (
		"Report",
		"Page",
		"Workspace",
		"Dashboard Chart",
		"Notification",
		"Server Script",
		"Print Format",
		"Client Script",
		"Web Page",
		"Web Form",
		"Web Template",
		"Website Theme",
	):
		if frappe.db.exists("DocType", dt) and frappe.db.has_column(dt, "module"):
			modules.update(frappe.get_all(dt, pluck="module", limit_page_length=0))

	return {m for m in modules if m}


def execute() -> None:
	"""Keep Module Defs for modules that are actually used by ferum_custom artifacts.

	Historically, multiple Module Defs were created for planned functional areas, but only
	`Ferum Custom` is actively used. Extra unused Module Defs can confuse navigation and
	module onboarding.
	"""
	if not frappe.db.exists("DocType", "Module Def"):
		return

	in_use = _get_modules_in_use()

	# Always keep the canonical module name used by the app code.
	in_use.add("Ferum Custom")

	existing = frappe.get_all(
		"Module Def",
		filters={"app_name": "ferum_custom"},
		fields=["name", "module_name"],
		limit_page_length=0,
	)

	# Ensure canonical module exists
	if not any(d.get("module_name") == "Ferum Custom" for d in existing):
		doc = frappe.new_doc("Module Def")
		doc.module_name = "Ferum Custom"
		doc.app_name = "ferum_custom"
		doc.custom = 0
		doc.insert(ignore_permissions=True)

	# Delete unused ones
	for d in existing:
		module_name = d.get("module_name")
		if not module_name or module_name in in_use:
			continue
		frappe.delete_doc("Module Def", d["name"], ignore_permissions=True, force=True)
