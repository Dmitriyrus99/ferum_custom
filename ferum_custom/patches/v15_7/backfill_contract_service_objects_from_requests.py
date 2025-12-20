from __future__ import annotations

import frappe


def _make_service_object_customer_required() -> None:
    """Enforce 'Service Object.customer' as required in DocField metadata (DB-stored DocType)."""
    if not frappe.db.exists("DocType", "Service Object"):
        return
    if not frappe.db.exists(
        "DocField",
        {"parent": "Service Object", "parenttype": "DocType", "fieldname": "customer"},
    ):
        return

    frappe.db.set_value(
        "DocField",
        {"parent": "Service Object", "parenttype": "DocType", "fieldname": "customer"},
        "reqd",
        1,
    )


def _ensure_service_object_customer(service_object: str, fallback_customer: str | None) -> str | None:
    so_customer = frappe.db.get_value("Service Object", service_object, "customer")
    if so_customer:
        return so_customer
    if fallback_customer:
        frappe.db.set_value("Service Object", service_object, "customer", fallback_customer)
        return fallback_customer
    return None


def execute() -> None:
    """Backfill ContractServiceObject links using existing Service Requests.

    The legacy system often kept object links only on Service Request.
    This patch derives (contract, service_object) pairs and creates ContractServiceObject rows.
    """
    if not frappe.db.exists("DocType", "ContractServiceObject"):
        return
    if not frappe.db.exists("DocType", "Service Request") or not frappe.db.exists("DocType", "Service Object"):
        return

    _make_service_object_customer_required()

    rows = frappe.get_all(
        "Service Request",
        filters={"contract": ["is", "set"], "service_object": ["is", "set"]},
        fields=["name", "contract", "service_object", "customer"],
        limit_page_length=0,
    )

    for r in rows:
        contract = r.get("contract")
        service_object = r.get("service_object")
        if not contract or not service_object:
            continue

        # Ensure the Service Object has a Customer (new invariant: 1 physical object == 1 Customer).
        so_customer = _ensure_service_object_customer(service_object, r.get("customer"))

        contract_customer = frappe.db.get_value("Contract", contract, "party_name")
        if contract_customer and so_customer and contract_customer != so_customer:
            # Data conflict: do not create an invalid link silently.
            # Leave it for manual resolution; requests remain the historical source.
            continue

        if frappe.db.exists(
            "ContractServiceObject", {"contract": contract, "service_object": service_object}
        ):
            continue

        doc = frappe.new_doc("ContractServiceObject")
        doc.contract = contract
        doc.service_object = service_object
        doc.status = "Active"
        doc.insert(ignore_permissions=True)

