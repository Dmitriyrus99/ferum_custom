from __future__ import annotations

import frappe


def execute() -> None:
    # Hide legacy Service Project link on Invoice (custom financial tracker).
    if frappe.db.exists("DocType", "Invoice") and frappe.db.exists(
        "DocField", {"parent": "Invoice", "parenttype": "DocType", "fieldname": "project"}
    ):
        frappe.db.set_value(
            "DocField",
            {"parent": "Invoice", "parenttype": "DocType", "fieldname": "project"},
            {"hidden": 1, "read_only": 1, "label": "Service Project (Legacy)"},
        )

    frappe.clear_cache()

