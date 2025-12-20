from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document


def _get_contract_customer(contract: Document) -> str:
    if getattr(contract, "party_type", None) and contract.party_type != "Customer":
        frappe.throw(_("Contract party_type must be Customer."))
    if not getattr(contract, "party_name", None):
        frappe.throw(_("Contract must have Customer (party_name)."))
    return contract.party_name


def create_sales_invoice_for_service_act(service_act: Document, *, manual: bool) -> str:
    if getattr(service_act, "sales_invoice", None):
        return service_act.sales_invoice

    contract = frappe.get_doc("Contract", service_act.contract)
    customer = _get_contract_customer(contract)

    company = getattr(contract, "company", None) or frappe.defaults.get_defaults().get("company")
    if not company:
        frappe.throw(_("Company is required to create Sales Invoice."))

    item_code = frappe.db.get_value(
        "Item",
        {"disabled": 0, "is_sales_item": 1},
        "name",
        order_by="modified desc",
    )
    if not item_code:
        frappe.throw(_("No sales Item found (Item.is_sales_item=1)."))

    invoice = frappe.new_doc("Sales Invoice")
    invoice.company = company
    invoice.customer = customer
    invoice.posting_date = date.today()
    invoice.remarks = f"Created from ServiceAct {service_act.name}"

    invoice.append(
        "items",
        {
            "item_code": item_code,
            "qty": 1,
            "rate": service_act.amount,
            "description": f"Services by Contract {service_act.contract} ({service_act.period_from}–{service_act.period_to})",
        },
    )

    invoice.insert(ignore_permissions=True)

    # We keep Draft by default to avoid blocking accounting validations (taxes/accounts).
    if not manual and getattr(contract, "document_mode", None) == "UPD_ONLY":
        # Optional auto-submit can be introduced later if needed.
        pass

    service_act.db_set("sales_invoice", invoice.name)
    if getattr(service_act, "schedule", None):
        frappe.db.set_value("ActSchedule", service_act.schedule, "status", "Invoiced")

    return invoice.name


def on_service_act_signed(service_act: Document) -> None:
    contract = frappe.get_doc("Contract", service_act.contract)
    mode = getattr(contract, "document_mode", None)

    if getattr(service_act, "schedule", None):
        frappe.db.set_value("ActSchedule", service_act.schedule, "status", "Signed")

    if mode == "UPD_ONLY":
        create_sales_invoice_for_service_act(service_act, manual=False)
