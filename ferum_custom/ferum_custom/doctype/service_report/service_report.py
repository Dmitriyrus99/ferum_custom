from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceReport(Document):
    def validate(self):
        self._calculate_totals()
        self._validate_attachments()
        self._validate_workflow_transitions()

    def on_submit(self):
        self._update_service_request_on_submit()

    def _calculate_totals(self) -> None:
        total_amount = 0.0

        for item in self.get("work_items") or []:
            hours = float(getattr(item, "hours", None) or 0)
            rate = float(getattr(item, "rate", None) or 0)
            row_total = hours * rate

            if hasattr(item, "total"):
                item.total = row_total

            total_amount += row_total

        if self.meta.has_field("total_amount"):
            self.total_amount = total_amount
        if self.meta.has_field("total_payable"):
            self.total_payable = total_amount

    def _validate_attachments(self) -> None:
        for item in self.get("documents") or []:
            if not getattr(item, "custom_attachment", None):
                frappe.throw(_("Attachment is required for all Document Items."))

    def _validate_workflow_transitions(self) -> None:
        if not self.meta.has_field("status") or self.is_new():
            return

        old_status = frappe.db.get_value(self.doctype, self.name, "status")
        if not old_status or old_status == self.status:
            return

        if old_status == "Draft" and self.status == "Submitted":
            return
        if old_status == "Submitted" and self.status in {"Approved", "Draft"}:
            return
        if old_status == "Approved" and self.status == "Archived":
            return
        if self.status == "Cancelled":
            if old_status not in {"Draft", "Submitted"}:
                frappe.throw(_("Service Report can only be Cancelled from Draft or Submitted status."))
            return

        frappe.throw(_(f"Invalid status transition from {old_status} to {self.status}."))

    def _update_service_request_on_submit(self) -> None:
        if not getattr(self, "service_request", None):
            return

        request_dt = "Service Request" if frappe.db.exists("DocType", "Service Request") else "ServiceRequest"
        sr = frappe.get_doc(request_dt, self.service_request)

        if sr.meta.has_field("linked_report"):
            sr.linked_report = self.name
        if sr.meta.has_field("status"):
            sr.status = "Completed"

        sr.save(ignore_permissions=True)
        frappe.msgprint(_("Service Request {0} updated and marked as Completed.").format(self.service_request))
