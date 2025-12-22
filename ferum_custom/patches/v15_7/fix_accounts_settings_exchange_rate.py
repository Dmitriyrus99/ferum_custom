from __future__ import annotations

import frappe


def execute():
    """Fix Accounts Settings exchange-rate configuration.

    ERPNext `erpnext.setup.utils.get_exchange_rate()` uses:
      - Accounts Settings.allow_stale
      - Accounts Settings.stale_days

    If they are missing/NULL, the function may crash before it can read Currency Exchange rows,
    breaking Sales/Purchase Invoice forms (they call get_exchange_rate during form load).
    """

    # Keep behavior predictable: do not allow stale beyond 30 days, but avoid None.
    frappe.db.set_single_value("Accounts Settings", "allow_stale", 0)
    frappe.db.set_single_value("Accounts Settings", "stale_days", 30)
