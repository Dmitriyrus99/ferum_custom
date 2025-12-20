from __future__ import annotations

from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document


def validate_contract_party_is_customer(
    contract: Document, method: str | None = None, *, set_party_type: bool = True
) -> None:
    """Enforce that Contract.party_type is Customer and party_name exists."""
    party_name = getattr(contract, "party_name", None)
    party_type = getattr(contract, "party_type", None)

    if party_name and set_party_type and party_type != "Customer":
        contract.party_type = "Customer"
        party_type = "Customer"

    if party_type and party_type != "Customer":
        frappe.throw(_("Contract party type must be Customer."))

    if party_name and not frappe.db.exists("Customer", party_name):
        frappe.throw(_("Customer {0} not found.").format(frappe.bold(party_name)))


def _get_project_name_for_contract(contract: Document) -> str:
    contract_code = getattr(contract, "contract_code", None)
    return contract_code or contract.name


def get_project_for_contract(contract_name: str) -> Optional[str]:
    if not contract_name:
        return None
    return frappe.db.get_value("Project", {"contract": contract_name}, "name")


def ensure_project_for_contract(contract: Document, method: str | None = None) -> Optional[str]:
    """Create/sync Project for Contract when Contract becomes Active, and enforce 1:1."""
    status = getattr(contract, "status", None)
    if status != "Active":
        return None

    existing = frappe.get_all("Project", filters={"contract": contract.name}, pluck="name", limit=2)
    if len(existing) > 1:
        frappe.throw(
            _("Multiple Projects are linked to Contract {0}: {1}").format(
                frappe.bold(contract.name), ", ".join(existing)
            )
        )

    if existing:
        project = frappe.get_doc("Project", existing[0])
        sync_project_from_contract(contract, project)
        project.save(ignore_permissions=True)
        return project.name

    project = frappe.new_doc("Project")
    project.project_name = _get_project_name_for_contract(contract)
    project.project_type = "External"

    if hasattr(project, "contract"):
        project.contract = contract.name

    sync_project_from_contract(contract, project)
    project.insert(ignore_permissions=True)
    return project.name


def sync_project_from_contract(contract: Document, project: Document) -> None:
    """Sync selected fields from Contract -> Project (best-effort if fields exist)."""
    if hasattr(project, "customer"):
        project.customer = getattr(contract, "party_name", None)

    if hasattr(project, "company") and hasattr(contract, "company"):
        project.company = getattr(contract, "company", None)

    if hasattr(project, "project_manager") and hasattr(contract, "project_manager"):
        project.project_manager = getattr(contract, "project_manager", None)

    if hasattr(project, "expected_start_date") and hasattr(contract, "start_date"):
        project.expected_start_date = getattr(contract, "start_date", None)

    if hasattr(project, "expected_end_date") and hasattr(contract, "end_date"):
        project.expected_end_date = getattr(contract, "end_date", None)


def validate_project_has_contract(project: Document, method: str | None = None) -> None:
    """For External Projects enforce Contract link (target model)."""
    if getattr(project, "project_type", None) != "External":
        return

    contract = getattr(project, "contract", None)
    if not contract:
        frappe.throw(_("External Project must have Contract linked."))


def validate_project_unique_contract(project: Document, method: str | None = None) -> None:
    contract = getattr(project, "contract", None)
    if not contract:
        return

    other = frappe.db.get_value(
        "Project",
        {"contract": contract, "name": ["!=", project.name]},
        "name",
    )
    if other:
        frappe.throw(
            _("Contract {0} is already linked to Project {1}.").format(
                frappe.bold(contract), frappe.bold(other)
            )
        )
