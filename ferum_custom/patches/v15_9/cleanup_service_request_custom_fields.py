from __future__ import annotations

import frappe


def _hide_custom_field(dt: str, fieldname: str, *, label: str, description: str) -> None:
	name = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
	if not name:
		return

	frappe.db.set_value(
		"Custom Field",
		name,
		{
			"label": label,
			"description": description,
			"hidden": 1,
			"read_only": 1,
		},
		update_modified=False,
	)


def execute() -> None:
	# Legacy fields kept for backward compatibility (service schedules/contract migration),
	# but hidden from the UI to keep the new Service Request UX minimal.
	_hide_custom_field(
		"Service Request",
		"contract",
		label="Договор (legacy)",
		description="Скрыто. Историческое поле для миграций/графиков обслуживания.",
	)
	_hide_custom_field(
		"Service Request",
		"erpnext_project",
		label="Проект (ERPNext, legacy)",
		description="Скрыто. Используйте поле «Проект» (erp_project).",
	)

	frappe.clear_cache()

