from __future__ import annotations

import frappe


def execute():
    report_name = "Service Requests by Project"

    query = (
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
                "ref_doctype": "Service Request",
                "report_type": "Query Report",
            }
        )

    report.module = "Ferum Custom"
    report.ref_doctype = "Service Request"
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
