from __future__ import annotations

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document


class ActSchedule(Document):
    def validate(self) -> None:
        self._validate_period()
        self._fill_snapshots()
        self._compute_planned_submit_date()

    def _validate_period(self) -> None:
        if self.period_from and self.period_to and self.period_to < self.period_from:
            frappe.throw(_("Period To must be greater or equal to Period From."))

    def _fill_snapshots(self) -> None:
        if not self.contract:
            return

        contract = frappe.get_doc("Contract", self.contract)
        if hasattr(contract, "submission_channel") and not self.submission_channel:
            self.submission_channel = contract.submission_channel
        if hasattr(contract, "document_mode") and not self.document_mode:
            self.document_mode = contract.document_mode

        if not self.project and frappe.db.has_column("Project", "contract"):
            project = frappe.db.get_value("Project", {"contract": self.contract}, "name")
            if project:
                self.project = project

    def _compute_planned_submit_date(self) -> None:
        if not self.period_to or not self.contract:
            return

        contract = frappe.get_doc("Contract", self.contract)
        deadline_day = getattr(contract, "acts_deadline_day", None)
        if not deadline_day:
            return

        if not (1 <= int(deadline_day) <= 31):
            frappe.throw(_("Acts Deadline Day must be between 1 and 31."))

        year = self.period_to.year
        month = self.period_to.month
        last_day = calendar.monthrange(year, month)[1]
        day = min(int(deadline_day), last_day)
        self.planned_submit_date = date(year, month, day)

