import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate, add_days, add_months, add_years, getdate

class MaintenanceSchedule(Document):
    pass

@frappe.whitelist()
def generate_service_requests_from_schedule():
    today = getdate(nowdate())
    
    # Get all active Maintenance Schedules that are due
    due_schedules = frappe.get_all(
        "MaintenanceSchedule",
        filters={
            "next_due_date": ["<=", today]
        },
        fields=["name", "frequency", "next_due_date", "project", "customer"]
    )

    for schedule_data in due_schedules:
        schedule_doc = frappe.get_doc("MaintenanceSchedule", schedule_data.name)
        
        if not schedule_doc.service_objects:
            frappe.log_error(f"Maintenance Schedule {schedule_doc.name} has no linked Service Objects.", "Maintenance Schedule Generator")
            continue

        for item in schedule_doc.service_objects:
            try:
                # Create Service Request for each Service Object in the schedule
                service_request = frappe.new_doc("ServiceRequest")
                service_request.title = f"Scheduled Maintenance for {item.service_object} ({schedule_doc.schedule_name})"
                service_request.description = item.description or f"Routine maintenance as per schedule {schedule_doc.name}."
                service_request.service_object = item.service_object
                service_request.project = schedule_doc.project
                service_request.customer = schedule_doc.customer
                service_request.type = "Routine"
                service_request.priority = "Low"
                service_request.status = "Open"
                service_request.insert(ignore_permissions=True) # Insert ignoring permissions for scheduled job
                service_request.submit()
                frappe.log_by_page(f"Service Request {service_request.name} generated from Maintenance Schedule {schedule_doc.name}", "Maintenance Schedule Generator")

            except Exception as e:
                frappe.log_error(f"Failed to generate Service Request for {item.service_object} from schedule {schedule_doc.name}: {e}", "Maintenance Schedule Generator Error")

        # Update next_due_date for the schedule
        if schedule_doc.frequency == "Daily":
            schedule_doc.next_due_date = add_days(schedule_doc.next_due_date, 1)
        elif schedule_doc.frequency == "Weekly":
            schedule_doc.next_due_date = add_days(schedule_doc.next_due_date, 7)
        elif schedule_doc.frequency == "Monthly":
            schedule_doc.next_due_date = add_months(schedule_doc.next_due_date, 1)
        elif schedule_doc.frequency == "Quarterly":
            schedule_doc.next_due_date = add_months(schedule_doc.next_due_date, 3)
        elif schedule_doc.frequency == "Annually":
            schedule_doc.next_due_date = add_years(schedule_doc.next_due_date, 1)
        
        schedule_doc.last_generated_date = today
        schedule_doc.save(ignore_permissions=True)
        frappe.db.commit()
