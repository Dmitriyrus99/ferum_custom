from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
    # Some sites have a non-null DB column `tabContract.contract_year` without DocField,
    # which breaks inserts. Create a proper Custom Field so Frappe includes it in inserts.
    if not frappe.db.exists("DocType", "Contract"):
        return

    if frappe.db.exists(
        "DocField",
        {"parent": "Contract", "parenttype": "DocType", "fieldname": "contract_year"},
    ):
        return

    current_year = frappe.utils.now_datetime().year

    create_custom_fields(
        {
            "Contract": [
                {
                    "fieldname": "contract_year",
                    "label": "Contract Year",
                    "fieldtype": "Int",
                    "reqd": 1,
                    "default": current_year,
                    "insert_after": "start_date",
                }
            ]
        },
        ignore_validate=True,
    )

    frappe.clear_cache(doctype="Contract")

