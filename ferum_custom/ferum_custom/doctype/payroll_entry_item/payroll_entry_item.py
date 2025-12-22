from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class PayrollEntryItem(Document):
    def validate(self):
        base_salary = float(getattr(self, "base_salary", None) or 0)
        advance = float(getattr(self, "advance", None) or 0)
        self.net_salary = base_salary - advance
        if self.net_salary < 0:
            frappe.throw(_("Net Salary cannot be negative. Advance amount exceeds Base Salary."))
