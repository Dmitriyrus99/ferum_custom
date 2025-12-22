from __future__ import annotations

import frappe


def execute():
    report_name = "Invoices by Project"

    query = (
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
    )

    if frappe.db.exists("Report", report_name):
        report = frappe.get_doc("Report", report_name)
    else:
        report = frappe.get_doc(
            {
                "doctype": "Report",
                "report_name": report_name,
                "is_standard": "No",
                "module": "Ferum Custom",
                "ref_doctype": "Invoice",
                "report_type": "Query Report",
            }
        )

    report.module = "Ferum Custom"
    report.ref_doctype = "Invoice"
    report.report_type = "Query Report"
    report.is_standard = report.is_standard or "No"
    report.disabled = 0
    report.query = query

    existing = {f.fieldname for f in (report.get("filters") or []) if getattr(f, "fieldname", None)}
    if "project" not in existing:
        report.append(
            "filters",
            {
                "fieldname": "project",
                "label": "Project",
                "fieldtype": "Link",
                "options": "Service Project",
                "mandatory": 0,
                "wildcard_filter": 0,
                "default": "",
            },
        )

    if report.is_new():
        report.insert(ignore_permissions=True)
    else:
        report.save(ignore_permissions=True)
