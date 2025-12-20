import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate, add_hours, add_days, getdate
import requests
import json

class ServiceRequest(Document):
    def validate(self):
        self.set_customer_and_project()
        self.validate_workflow_transitions()
        self.calculate_sla_deadline()

    def on_update(self):
        self.check_sla_breach()

    def set_customer_and_project(self):
        if getattr(self, "contract", None):
            contract = frappe.get_doc("Contract", self.contract)
            if contract.party_type and contract.party_type != "Customer":
                frappe.throw(_("Contract party_type must be Customer."))
            if contract.party_name:
                self.customer = contract.party_name

            if frappe.db.has_column("Project", "contract"):
                self.erpnext_project = frappe.db.get_value("Project", {"contract": contract.name}, "name")
            return

        if self.service_object:
            service_object_doc = frappe.get_doc("ServiceObject", self.service_object)
            self.customer = service_object_doc.customer
            # Legacy linkage (deprecated)
            if hasattr(self, "project"):
                self.project = getattr(service_object_doc, "project", None)

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
            self.sla_deadline = add_hours(self.creation, 4) # 4 hours for high emergency
        elif self.type == "Emergency" and self.priority == "Medium":
            self.sla_deadline = add_hours(self.creation, 8) # 8 hours for medium emergency
        elif self.type == "Routine" and self.priority == "High":
            self.sla_deadline = add_days(self.creation, 1) # 1 day for routine high
        else:
            self.sla_deadline = add_days(self.creation, 3) # 3 days for others

    def check_sla_breach(self):
        if self.status not in ["Completed", "Closed"] and self.sla_deadline and getdate(nowdate()) > getdate(self.sla_deadline):
            message = f"SLA for Service Request {self.name} has been breached! Title: {self.title}. Priority: {self.priority}. Due: {self.sla_deadline}"
            frappe.msgprint(_(message))
            frappe.log_error(message, "SLA Breach Alert")

            # Send Telegram notification (assuming FastAPI backend is running and accessible)
            # In a real system, you would get the chat_id from user settings or a config DocType
            # TODO: Replace placeholders with actual configuration values (e.g., from a custom settings DocType)
            telegram_chat_id = 123456789 # REPLACE WITH ACTUAL CHAT ID OF ADMIN/DEPT HEAD
            fastapi_backend_url = "http://localhost:8000/api/v1/send_telegram_notification" # Adjust if FastAPI is on different host/port
            
            try:
                # This requires a valid JWT token from the FastAPI backend for authentication
                # TODO: Implement secure way to get/store this token
                headers = {"Authorization": "Bearer YOUR_FASTAPI_JWT_TOKEN"} # REPLACE WITH ACTUAL JWT TOKEN
                payload = {"chat_id": telegram_chat_id, "text": message}
                response = requests.post(fastapi_backend_url, headers=headers, json=payload)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                frappe.log_by_page(f"SLA breach notification sent to Telegram for {self.name}", "SLA Notification")
            except requests.exceptions.RequestException as e:
                frappe.log_error(f"Failed to send SLA breach Telegram notification for {self.name}: {e}", "SLA Notification Error")

            # Send Email notification
            # TODO: Determine recipient email addresses (e.g., from user roles, project managers, etc.)
            recipient_email = "admin@example.com" # REPLACE WITH ACTUAL RECIPIENT EMAIL
            subject = f"SLA Breach Alert: Service Request {self.name}"
            body = f"""Dear Team,

The Service Level Agreement for Service Request {self.name} has been breached.

Details:
Title: {self.title}
Priority: {self.priority}
Due Date: {self.sla_deadline}

Please take immediate action.

Regards,
System"""
            
            try:
                frappe.sendmail(recipients=recipient_email, subject=subject, message=body)
                frappe.log_by_page(f"SLA breach email notification sent for {self.name}", "SLA Notification")
            except Exception as e:
                frappe.log_error(f"Failed to send SLA breach email notification for {self.name}: {e}", "SLA Notification Error")
