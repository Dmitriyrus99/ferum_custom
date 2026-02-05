from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from ferum_custom.services.acts import create_sales_invoice_for_service_act, on_service_act_signed


class ServiceAct(Document):
	def validate(self) -> None:
		self._validate_period()
		self._fill_from_contract()
		self._fill_from_schedule()

	def on_update(self) -> None:
		before = self.get_doc_before_save()
		if not before:
			return
		if before.status != self.status and self.status == "Signed":
			on_service_act_signed(self)

	def _validate_period(self) -> None:
		if self.period_from and self.period_to and self.period_to < self.period_from:
			frappe.throw(_("Period To must be greater or equal to Period From."))

	def _fill_from_contract(self) -> None:
		if not self.contract:
			return
		contract = frappe.get_doc("Contract", self.contract)
		if getattr(contract, "party_type", None) and contract.party_type != "Customer":
			frappe.throw(_("Contract party_type must be Customer."))
		if getattr(contract, "party_name", None):
			self.customer = contract.party_name

	def _fill_from_schedule(self) -> None:
		if not self.schedule:
			return
		schedule = frappe.get_doc("ActSchedule", self.schedule)

		if not self.contract:
			self.contract = schedule.contract
		if not self.project:
			self.project = schedule.project

		if not self.period_from:
			self.period_from = schedule.period_from
		if not self.period_to:
			self.period_to = schedule.period_to

		if not self.amount:
			self.amount = schedule.planned_amount

	@frappe.whitelist()
	def create_sales_invoice(self) -> str:
		contract = frappe.get_doc("Contract", self.contract)
		mode = getattr(contract, "document_mode", None)
		if mode != "ACT_PLUS_INVOICE":
			frappe.throw(_("Manual invoice creation is intended for ACT_PLUS_INVOICE contracts."))
		return create_sales_invoice_for_service_act(self, manual=True)
