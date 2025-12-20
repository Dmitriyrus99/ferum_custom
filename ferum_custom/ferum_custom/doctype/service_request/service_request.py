from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceRequest(Document):
    def validate(self):
        self._sync_contract_customer_project()

    def _service_object_dt(self) -> str:
        if frappe.db.exists("DocType", "Service Object"):
            return "Service Object"
        return "ServiceObject"

    def _sync_contract_customer_project(self) -> None:
        # If contract is not set but service_object is known, try to infer contract from active link.
        if not getattr(self, "contract", None) and getattr(self, "service_object", None) and self.meta.has_field(
            "contract"
        ):
            links = frappe.get_all(
                "ContractServiceObject",
                filters={"service_object": self.service_object, "status": "Active"},
                pluck="contract",
            )
            self.contract = _pick_contract_for_service_object(
                service_object=self.service_object,
                contracts=links,
                company=getattr(self, "company", None),
            )

        if getattr(self, "contract", None):
            contract = frappe.get_doc("Contract", self.contract)
            if contract.party_type and contract.party_type != "Customer":
                frappe.throw(_("Contract party_type must be Customer."))

            if contract.party_name:
                self.customer = contract.party_name

            if self.meta.has_field("erpnext_project") and frappe.db.has_column("Project", "contract"):
                self.erpnext_project = frappe.db.get_value("Project", {"contract": contract.name}, "name")

            if getattr(self, "service_object", None):
                so_customer = frappe.db.get_value(self._service_object_dt(), self.service_object, "customer")
                if so_customer and contract.party_name and so_customer != contract.party_name:
                    frappe.throw(
                        _("Service Object customer {0} must match Contract customer {1}.").format(
                            frappe.bold(so_customer), frappe.bold(contract.party_name)
                        )
                    )


def _pick_contract_for_service_object(*, service_object: str, contracts: list[str], company: str | None) -> str | None:
    """Deterministic inference when Service Object can belong to multiple active contracts.

    Priority:
    1) If only one contract -> use it
    2) If company is known -> choose contract with same company
    3) Choose most recent by (start_date desc, modified desc, name desc)
    If still ambiguous/empty -> return None (user must select).
    """
    contracts = [c for c in contracts if c]
    if not contracts:
        return None
    if len(contracts) == 1:
        return contracts[0]

    if company and frappe.db.has_column("Contract", "company"):
        same_company = frappe.get_all(
            "Contract",
            filters={"name": ["in", contracts], "company": company},
            pluck="name",
        )
        if len(same_company) == 1:
            return same_company[0]
        if len(same_company) > 1:
            contracts = same_company

    # Prefer most recent contract
    row = frappe.db.sql(
        """
        select name
        from tabContract
        where name in %(names)s
        order by ifnull(start_date, '1900-01-01') desc, modified desc, name desc
        limit 1
        """,
        {"names": tuple(contracts)},
    )
    return row[0][0] if row else None
