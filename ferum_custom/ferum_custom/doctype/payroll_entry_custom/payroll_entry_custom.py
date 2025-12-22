from __future__ import annotations

from frappe.model.document import Document


class PayrollEntryCustom(Document):
    def validate(self):
        self._calculate_total_payroll_amount()

    def _calculate_total_payroll_amount(self) -> None:
        total = 0.0
        for item in self.get("employees") or []:
            total += float(getattr(item, "net_salary", None) or 0)
        if self.meta.has_field("total_payroll_amount"):
            self.total_payroll_amount = total
