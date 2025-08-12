import frappe
from frappe.model.document import Document
from frappe import _

class ServiceReport(Document):
    def validate(self):
        self.calculate_total_amount()
        self.validate_attachments()

    def on_submit(self):
        self.update_service_request_on_submit()

    def calculate_total_amount(self):
        self.total_amount = 0
        for item in self.work_items:
            item.total = item.hours * item.rate
            self.total_amount += item.total

    def validate_attachments(self):
        for item in self.documents:
            if not item.custom_attachment:
                frappe.throw(_("Attachment is required for all Document Items."))

    def update_service_request_on_submit(self):
        if self.service_request:
            service_request_doc = frappe.get_doc("ServiceRequest", self.service_request)
            service_request_doc.linked_report = self.name
            service_request_doc.status = "Completed"
            service_request_doc.save()
            frappe.msgprint(_(f"Service Request {self.service_request} updated and marked as Completed."))