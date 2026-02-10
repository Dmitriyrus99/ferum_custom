from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ProjectSite(Document):
	def validate(self):
		self._sync_from_contract()
		self._validate_unique_within_contract()

	def _sync_from_contract(self) -> None:
		contract = str(getattr(self, "contract", "") or "").strip()
		if not contract:
			return
		if not frappe.db.exists("Contract", contract):
			frappe.throw(_("Contract not found: {0}.").format(frappe.bold(contract)))

		row = frappe.db.get_value(
			"Contract",
			contract,
			["party_type", "party_name", "company"],
			as_dict=True,
		)
		party_type = str((row or {}).get("party_type") or "").strip()
		party_name = str((row or {}).get("party_name") or "").strip()
		company = str((row or {}).get("company") or "").strip()

		if party_type and party_type != "Customer":
			frappe.throw(_("Contract party_type must be Customer."))

		if party_name and self.meta.has_field("customer"):
			if not getattr(self, "customer", None):
				self.customer = party_name
			elif str(getattr(self, "customer", "") or "").strip() != party_name:
				frappe.throw(
					_("Project Site customer must match Contract customer {0}.").format(
						frappe.bold(party_name)
					)
				)

		if company and self.meta.has_field("company") and not getattr(self, "company", None):
			self.company = company

		# Best-effort: fill Project via Contract -> Project 1:1 relation.
		if self.meta.has_field("project") and not getattr(self, "project", None):
			proj = frappe.db.get_value("Project", {"contract": contract}, "name")
			if proj:
				self.project = proj

	def _validate_unique_within_contract(self) -> None:
		"""Prevent obvious duplicates within the same contract.

		DB-level composite unique index will be added via patch later.
		"""
		contract = str(getattr(self, "contract", "") or "").strip()
		address = str(getattr(self, "address", "") or "").strip()
		if not contract or not address:
			return

		other = frappe.db.get_value(
			self.doctype,
			{"contract": contract, "address": address, "name": ["!=", self.name]},
			"name",
		)
		if other:
			frappe.throw(
				_("Duplicate Project Site address within Contract. Existing: {0}.").format(frappe.bold(other))
			)
