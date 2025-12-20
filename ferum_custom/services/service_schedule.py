from __future__ import annotations

import frappe
from frappe.utils import add_days, add_months, add_years, nowdate


def _get_schedule_doctype() -> str | None:
    for dt in ("Service Maintenance Schedule", "MaintenanceSchedule", "Maintenance Schedule"):
        if frappe.db.exists("DocType", dt):
            return dt
    return None


def _get_schedule_item_doctype() -> str | None:
    for dt in ("Service Maintenance Schedule Item", "MaintenanceScheduleItem", "Maintenance Schedule Detail"):
        if frappe.db.exists("DocType", dt):
            return dt
    return None


def _get_service_request_doctype() -> str | None:
    for dt in ("Service Request", "ServiceRequest"):
        if frappe.db.exists("DocType", dt):
            return dt
    return None


@frappe.whitelist()
def generate_service_requests_from_schedule() -> None:
    schedule_dt = _get_schedule_doctype()
    request_dt = _get_service_request_doctype()
    if not schedule_dt or not request_dt:
        return

    today = nowdate()
    schedule_names = frappe.get_all(
        schedule_dt,
        filters={"next_due_date": ["<=", today], "docstatus": 0},
        pluck="name",
    )

    for schedule_name in schedule_names:
        schedule = frappe.get_doc(schedule_dt, schedule_name)
        if schedule.get("end_date") and schedule.end_date < today:
            continue

        for item in schedule.get("items") or []:
            service_request = frappe.new_doc(request_dt)
            service_request.service_object = item.service_object
            service_request.title = f"Scheduled Maintenance for {item.service_object} ({schedule.schedule_name})"
            service_request.description = (
                getattr(item, "description", None)
                or f"Routine maintenance as per schedule {schedule.schedule_name}"
            )
            service_request.status = "Open"

            if getattr(schedule, "contract", None) and service_request.meta.has_field("contract"):
                service_request.contract = schedule.contract
                if service_request.meta.has_field("erpnext_project"):
                    service_request.erpnext_project = getattr(schedule, "erpnext_project", None)

            service_request.save(ignore_permissions=True)

        # Update next_due_date
        if schedule.frequency == "Daily":
            schedule.next_due_date = add_days(schedule.next_due_date, 1)
        elif schedule.frequency == "Weekly":
            schedule.next_due_date = add_days(schedule.next_due_date, 7)
        elif schedule.frequency == "Monthly":
            schedule.next_due_date = add_months(schedule.next_due_date, 1)
        elif schedule.frequency == "Annually":
            schedule.next_due_date = add_years(schedule.next_due_date, 1)

        schedule.save(ignore_permissions=True)

    frappe.db.commit()

