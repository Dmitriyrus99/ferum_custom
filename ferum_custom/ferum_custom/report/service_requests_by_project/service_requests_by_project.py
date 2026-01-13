from __future__ import annotations

from typing import Any

import frappe


def execute(filters: dict | None = None) -> tuple[list[str], list[list[Any]]]:
	filters = filters or {}
	project = (filters.get("project") or "").strip()

	conditions: list[str] = []
	values: list[Any] = []
	if project:
		conditions.append("project = %s")
		values.append(project)

	where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

	columns = [
		"Заявка:Link/Service Request:150",
		"Проект:Link/Service Project:180",
		"Статус:Data:120",
		"Приоритет:Data:120",
		"Назначено:Link/User:180",
		"Изменен:Datetime:160",
	]

	rows = frappe.db.sql(
		f"""
		select
			name,
			project,
			status,
			priority,
			assigned_to,
			modified
		from `tabService Request`
		{where}
		order by modified desc
		""",
		values,
		as_list=True,
	)
	return columns, rows

