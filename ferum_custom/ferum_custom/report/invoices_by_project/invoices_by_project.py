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
		"Счет:Link/Invoice:150",
		"Проект:Link/Service Project:180",
		"Контрагент:Data:180",
		"Тип контрагента:Data:140",
		"Статус:Data:120",
		"Сумма:Currency:120",
		"Дата счета:Date:120",
		"Изменен:Datetime:160",
	]

	rows = frappe.db.sql(
		f"""
		select
			name,
			project,
			counterparty_name,
			counterparty_type,
			status,
			amount,
			invoice_date,
			modified
		from `tabInvoice`
		{where}
		order by modified desc
		""",
		values,
		as_list=True,
	)
	return columns, rows

