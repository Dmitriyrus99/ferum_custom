from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceMaintenanceSchedule(Document):
	def validate(self):
		self._sync_contract_customer_project()

	def _sync_contract_customer_project(self):
		if not getattr(self, "contract", None):
			return

		contract = frappe.get_doc("Contract", self.contract)
		if contract.party_type and contract.party_type != "Customer":
			frappe.throw(_("Contract party_type must be Customer."))

		if getattr(contract, "party_name", None):
			self.customer = contract.party_name

		if self.meta.has_field("erpnext_project") and frappe.db.has_column("Project", "contract"):
			self.erpnext_project = frappe.db.get_value("Project", {"contract": contract.name}, "name")
