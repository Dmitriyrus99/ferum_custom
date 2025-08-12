import frappe
from frappe.model.document import Document
from frappe import _

class ServiceRequest(Document):
    def validate(self):
        self.set_customer_and_project()
        self.validate_workflow_transitions()
        self.calculate_sla_deadline()

    def on_update(self):
        self.check_sla_breach()

    def set_customer_and_project(self):
        if self.service_object:
            service_object_doc = frappe.get_doc("ServiceObject", self.service_object)
            self.customer = service_object_doc.customer
            self.project = service_object_doc.project

    def validate_workflow_transitions(self):
        # Implement strict workflow transitions based on Technical_Specification_full.md
        # [*] --> Open
        # Open --> InProgress : Assign Engineer
        # InProgress --> Completed : Submit Service Report
        # Completed --> Closed : Manager Approval

        # Get old status if document is not new
        old_status = frappe.db.get_value("ServiceRequest", self.name, "status") if not self.is_new() else None

        if old_status == "Open" and self.status == "In Progress" and not self.assigned_to:
            frappe.throw(_("Cannot set status to 'In Progress' without assigning an engineer."))
        elif old_status == "In Progress" and self.status == "Completed" and not self.linked_report:
            frappe.throw(_("Cannot set status to 'Completed' without linking a Service Report."))
        elif old_status == "Completed" and self.status == "Closed" and frappe.session.user != "Administrator": # Placeholder for Manager Approval
            # In a real scenario, this would check for a specific role or user
            frappe.throw(_("Only a Manager can close a Service Request."))
        # Add more transitions as needed based on the full workflow diagram
        # For example, Open -> Cancelled, In Progress -> Cancelled, Completed -> In Progress (for rework)
        # For simplicity, I'm only adding the main positive flow and a basic check for closing.

    def calculate_sla_deadline(self):
        # Placeholder for SLA calculation logic
        # This would typically involve business hours, holidays, etc.
        # For now, a simple calculation based on type and priority
        if self.type == "Emergency" and self.priority == "High":
            self.sla_deadline = frappe.utils.add_hours(self.creation, 4) # 4 hours for high emergency
        elif self.type == "Emergency" and self.priority == "Medium":
            self.sla_deadline = frappe.utils.add_hours(self.creation, 8) # 8 hours for medium emergency
        elif self.type == "Routine" and self.priority == "High":
            self.sla_deadline = frappe.utils.add_days(self.creation, 1) # 1 day for routine high
        else:
            self.sla_deadline = frappe.utils.add_days(self.creation, 3) # 3 days for others

    def check_sla_breach(self):
        if self.status not in ["Completed", "Closed"] and self.sla_deadline and frappe.utils.now() > self.sla_deadline:
            frappe.msgprint(_(f"SLA for Service Request {self.name} has been breached!"))
            # In a real system, this would trigger an escalation or notification
