from __future__ import annotations

import frappe


def _upsert_query_report(
	report_name: str,
	*,
	ref_doctype: str,
	query: str,
	filters: list[dict] | None = None,
) -> None:
	if frappe.db.exists("Report", report_name):
		report = frappe.get_doc("Report", report_name)
	else:
		report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": report_name,
				"is_standard": "No",
				"module": "Ferum Custom",
				"ref_doctype": ref_doctype,
				"report_type": "Query Report",
			}
		)

	report.module = "Ferum Custom"
	report.ref_doctype = ref_doctype
	report.report_type = "Query Report"
	report.is_standard = report.is_standard or "No"
	report.disabled = 0
	report.query = query

	if filters is not None:
		report.set("filters", [])
		for row in filters:
			report.append("filters", row)

	if report.is_new():
		report.insert(ignore_permissions=True)
	else:
		report.save(ignore_permissions=True)


def execute():
	_upsert_query_report(
		"Open Service Requests by Engineer",
		ref_doctype="Service Request",
		query=(
			"SELECT "
			"COALESCE(assigned_to, 'Не назначено') AS \"Инженер:Data:200\", "
			"COUNT(*) AS \"Открытых заявок:Int:100\" "
			"FROM `tabService Request` "
			"WHERE status IN ('Open', 'In Progress') "
			"GROUP BY assigned_to "
			"ORDER BY COUNT(*) DESC"
		),
		filters=[],
	)

	_upsert_query_report(
		"Unassigned Service Requests",
		ref_doctype="Service Request",
		query=(
			"SELECT "
			"name AS \"Заявка:Link/Service Request:150\", "
			"status AS \"Статус:Data:120\", "
			"priority AS \"Приоритет:Data:120\", "
			"modified AS \"Изменен:Datetime:160\" "
			"FROM `tabService Request` "
			"WHERE (assigned_to IS NULL OR assigned_to = '') "
			"AND status IN ('Open', 'In Progress') "
			"ORDER BY modified DESC"
		),
		filters=[],
	)

	_upsert_query_report(
		"Service Requests by Project",
		ref_doctype="Service Request",
		query=(
			"SELECT "
			"name AS \"Заявка:Link/Service Request:150\", "
			"project AS \"Проект:Link/Service Project:180\", "
			"status AS \"Статус:Data:120\", "
			"priority AS \"Приоритет:Data:120\", "
			"assigned_to AS \"Назначено:Link/User:180\", "
			"modified AS \"Изменен:Datetime:160\" "
			"FROM `tabService Request` "
			"WHERE ("
			"  %(project)s IS NULL OR %(project)s = '' OR project = %(project)s"
			") "
			"ORDER BY modified DESC"
		),
		filters=[
			{
				"fieldname": "project",
				"label": "Project",
				"fieldtype": "Link",
				"options": "Service Project",
				"mandatory": 0,
				"wildcard_filter": 0,
				"default": "",
			},
		],
	)

	_upsert_query_report(
		"Invoices by Project",
		ref_doctype="Invoice",
		query=(
			"SELECT "
			"name AS \"Счет:Link/Invoice:150\", "
			"project AS \"Проект:Link/Service Project:180\", "
			"counterparty_name AS \"Контрагент:Data:180\", "
			"counterparty_type AS \"Тип контрагента:Data:140\", "
			"status AS \"Статус:Data:120\", "
			"amount AS \"Сумма:Currency:120\", "
			"invoice_date AS \"Дата счета:Date:120\", "
			"modified AS \"Изменен:Datetime:160\" "
			"FROM `tabInvoice` "
			"WHERE ("
			"  %(project)s IS NULL OR %(project)s = '' OR project = %(project)s"
			") "
			"ORDER BY modified DESC"
		),
		filters=[
			{
				"fieldname": "project",
				"label": "Project",
				"fieldtype": "Link",
				"options": "Service Project",
				"mandatory": 0,
				"wildcard_filter": 0,
				"default": "",
			},
		],
	)

