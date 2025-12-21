import frappe
from frappe.utils import add_days, add_months, add_years, nowdate


@frappe.whitelist()
def generate_service_requests_from_schedule():
    today = nowdate()
    schedule_names = frappe.get_all(
        "MaintenanceSchedule",
        filters={"next_due_date": ["<=", today], "docstatus": 0},
        pluck="name",
    )

    for schedule_name in schedule_names:
        schedule = frappe.get_doc("MaintenanceSchedule", schedule_name)
        if schedule.end_date and schedule.end_date < today:
            # Schedule has ended, skip it
            continue

        for item in schedule.get("items") or []:
            try:
                service_request = frappe.new_doc("ServiceRequest")
                service_request.service_object = item.service_object
                if getattr(schedule, "contract", None):
                    service_request.contract = schedule.contract
                    service_request.erpnext_project = getattr(
                        schedule, "erpnext_project", None
                    )
                else:
                    service_request.customer = schedule.customer

                service_request.title = f"Scheduled Maintenance for {item.service_object} ({schedule.schedule_name})"
                service_request.description = (
                    item.description
                    or f"Routine maintenance as per schedule {schedule.schedule_name}"
                )
                service_request.status = "Open"
                service_request.save(ignore_permissions=True)
                frappe.db.commit()
                frappe.log_by_activity(
                    doctype="ServiceRequest",
                    name=service_request.name,
                    text=f"Created from Maintenance Schedule {schedule.name}",
                    status="Success",
                )
                frappe.msgprint(
                    f"Service Request {service_request.name} created for {item.service_object}"
                )
            except Exception as e:
                frappe.log_error(
                    f"Failed to create Service Request from Maintenance Schedule {schedule.name} for item {item.service_object}: {e}"
                )
                frappe.msgprint(
                    f"Failed to create Service Request for {item.service_object}: {e}",
                    alert=True,
                )

        # Update next_due_date for the schedule
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
