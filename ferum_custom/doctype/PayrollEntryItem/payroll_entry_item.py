import frappe
from frappe.model.document import Document

class PayrollEntryItem(Document):
    def validate(self):
        self.net_salary = self.base_salary - self.advance