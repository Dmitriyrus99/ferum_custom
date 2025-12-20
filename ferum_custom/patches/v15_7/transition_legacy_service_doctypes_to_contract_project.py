from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _dt_exists(dt: str) -> bool:
    return bool(dt and frappe.db.exists("DocType", dt))


def _service_object_dt() -> str:
    return "Service Object" if _dt_exists("Service Object") else "ServiceObject"


def _service_project_dt() -> str:
    return "Service Project" if _dt_exists("Service Project") else "ServiceProject"


def _service_request_dt() -> str:
    return "Service Request" if _dt_exists("Service Request") else "ServiceRequest"


def _service_schedule_dt() -> str:
    return (
        "Service Maintenance Schedule"
        if _dt_exists("Service Maintenance Schedule")
        else ("MaintenanceSchedule" if _dt_exists("MaintenanceSchedule") else "Maintenance Schedule")
    )


def _disable_service_project_mutations() -> None:
    dt = _service_project_dt()
    if not _dt_exists(dt):
        return

    # Keep read for history; disable write/create/delete for non-admin roles (idempotent).
    perms = frappe.get_all(
        "DocPerm",
        filters={"parent": dt, "parenttype": "DocType"},
        fields=["name", "role"],
    )
    for p in perms:
        if p.role in {"Administrator", "System Manager"}:
            continue
        frappe.db.set_value(
            "DocPerm",
            p.name,
            {
                "create": 0,
                "write": 0,
                "delete": 0,
                "submit": 0,
                "cancel": 0,
                "amend": 0,
            },
        )


def _hide_legacy_links() -> None:
    # Hide legacy Service Project links on related doctypes.
    so_dt = _service_object_dt()
    if _dt_exists(so_dt):
        frappe.db.set_value(
            "DocField",
            {"parent": so_dt, "parenttype": "DocType", "fieldname": "project"},
            {"hidden": 1, "read_only": 1, "label": "Service Project (Legacy)"},
        )

    sr_dt = _service_request_dt()
    if _dt_exists(sr_dt):
        frappe.db.set_value(
            "DocField",
            {"parent": sr_dt, "parenttype": "DocType", "fieldname": "project"},
            {"hidden": 1, "read_only": 1, "label": "Service Project (Legacy)"},
        )

    sched_dt = _service_schedule_dt()
    if _dt_exists(sched_dt) and frappe.db.exists(
        "DocField", {"parent": sched_dt, "parenttype": "DocType", "fieldname": "service_project"}
    ):
        frappe.db.set_value(
            "DocField",
            {"parent": sched_dt, "parenttype": "DocType", "fieldname": "service_project"},
            {"hidden": 1, "read_only": 1, "label": "Service Project (Legacy)"},
        )


def _ensure_custom_fields() -> None:
    sr_dt = _service_request_dt()
    sched_dt = _service_schedule_dt()

    custom_fields: dict[str, list[dict]] = {}

    if _dt_exists(sr_dt):
        custom_fields[sr_dt] = [
            {
                "fieldname": "contract",
                "label": "Contract",
                "fieldtype": "Link",
                "options": "Contract",
                "insert_after": "project",
            },
            {
                "fieldname": "erpnext_project",
                "label": "Project",
                "fieldtype": "Link",
                "options": "Project",
                "read_only": 1,
                "insert_after": "contract",
            },
        ]

    if _dt_exists(sched_dt):
        custom_fields[sched_dt] = [
            {
                "fieldname": "contract",
                "label": "Contract",
                "fieldtype": "Link",
                "options": "Contract",
                "insert_after": "service_project"
                if frappe.db.exists(
                    "DocField", {"parent": sched_dt, "parenttype": "DocType", "fieldname": "service_project"}
                )
                else "customer",
            },
            {
                "fieldname": "erpnext_project",
                "label": "Project",
                "fieldtype": "Link",
                "options": "Project",
                "read_only": 1,
                "insert_after": "contract",
            },
        ]

    # Invoice is a custom financial tracker; add Contract+Project fields even if file-sync is off.
    if _dt_exists("Invoice"):
        custom_fields["Invoice"] = [
            {
                "fieldname": "contract",
                "label": "Contract",
                "fieldtype": "Link",
                "options": "Contract",
                "insert_after": "project",
            },
            {
                "fieldname": "erpnext_project",
                "label": "Project",
                "fieldtype": "Link",
                "options": "Project",
                "read_only": 1,
                "insert_after": "contract",
            },
        ]

    if custom_fields:
        create_custom_fields(custom_fields, ignore_validate=True)


def _fix_contract_service_object_link_target() -> None:
    # Ensure ContractServiceObject.service_object points to the canonical Service Object doctype.
    if not _dt_exists("ContractServiceObject"):
        return

    target = _service_object_dt()
    frappe.db.set_value(
        "DocField",
        {"parent": "ContractServiceObject", "parenttype": "DocType", "fieldname": "service_object"},
        "options",
        target,
    )


def execute() -> None:
    _disable_service_project_mutations()
    _hide_legacy_links()
    _ensure_custom_fields()
    _fix_contract_service_object_link_target()
    frappe.clear_cache()

