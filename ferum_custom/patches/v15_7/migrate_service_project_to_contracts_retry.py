from __future__ import annotations

import frappe

from ferum_custom.patches.v15_7.migrate_service_project_to_contracts import (
    _backfill_refs,
    _ensure_project_for_contract,
    _get_or_create_contract_for_service_project,
    _link_objects,
)


def execute() -> None:
    if not frappe.db.exists("DocType", "Service Project"):
        return

    service_projects = frappe.get_all("Service Project", pluck="name")
    for sp_name in service_projects:
        # If contract already exists for this service project (contract_code), skip.
        if frappe.db.has_column("Contract", "contract_code") and frappe.db.get_value(
            "Contract", {"contract_code": sp_name}, "name"
        ):
            continue

        contract_name = _get_or_create_contract_for_service_project(sp_name)
        if not contract_name:
            continue

        erp_project = _ensure_project_for_contract(contract_name, sp_name)
        _link_objects(contract_name, sp_name)
        _backfill_refs(sp_name, contract_name, erp_project)

    frappe.db.commit()
    frappe.clear_cache()

