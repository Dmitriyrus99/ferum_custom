import frappe
from frappe.model.document import Document
from frappe import _

class PayrollEntryItem(Document):
    def validate(self):
        self.net_salary = self.base_salary - self.advance
        if self.net_salary < 0:
            frappe.throw(_("Net Salary cannot be negative. Advance amount exceeds Base Salary."))
