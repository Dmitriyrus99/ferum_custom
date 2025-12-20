from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ContractServiceObject(Document):
    def validate(self) -> None:
        self._validate_unique_pair()
        self._validate_contract_party()
        self._validate_customer_match()

    def _validate_unique_pair(self) -> None:
        other = frappe.db.get_value(
            "ContractServiceObject",
            {
                "contract": self.contract,
                "service_object": self.service_object,
                "name": ["!=", self.name],
            },
            "name",
        )
        if other:
            frappe.throw(
                _("Service Object {0} is already linked to Contract {1}.").format(
                    frappe.bold(self.service_object), frappe.bold(self.contract)
                )
            )

    def _validate_contract_party(self) -> None:
        party_type, party_name = frappe.db.get_value(
            "Contract", self.contract, ["party_type", "party_name"]
        ) or (None, None)
        if party_type and party_type != "Customer":
            frappe.throw(_("Contract party_type must be Customer for ContractServiceObject."))
        if party_name and not frappe.db.exists("Customer", party_name):
            frappe.throw(_("Customer {0} not found.").format(frappe.bold(party_name)))

    def _validate_customer_match(self) -> None:
        party_name = frappe.db.get_value("Contract", self.contract, "party_name")
        so_customer = frappe.db.get_value("ServiceObject", self.service_object, "customer")
        if party_name and so_customer and party_name != so_customer:
            frappe.throw(
                _("Service Object customer {0} must match Contract customer {1}.").format(
                    frappe.bold(so_customer), frappe.bold(party_name)
                )
            )

