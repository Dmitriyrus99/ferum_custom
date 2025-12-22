from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceProject(Document):
    def validate(self):
        self._validate_dates_and_amount()
        self._validate_unique_objects()

    def _validate_dates_and_amount(self) -> None:
        start_date = getattr(self, "start_date", None)
        end_date = getattr(self, "end_date", None)
        total_amount = getattr(self, "total_amount", None)

        if start_date and end_date and end_date < start_date:
            frappe.throw(_("End Date cannot be before Start Date."))

        if total_amount is not None and float(total_amount or 0) < 0:
            frappe.throw(_("Contract Amount cannot be negative."))

    def _validate_unique_objects(self) -> None:
        if not self.meta.has_field("objects"):
            return

        seen: set[str] = set()
        for item in self.get("objects") or []:
            service_object = getattr(item, "service_object", None)
            if not service_object:
                continue
            if service_object in seen:
                frappe.throw(_("Service Object {0} is duplicated in this project.").format(service_object))
            seen.add(service_object)
