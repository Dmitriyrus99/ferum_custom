from __future__ import annotations

from pathlib import Path

import frappe
from frappe.modules.import_file import get_file_path


def execute():
    """Export missing DocType JSON files to the app folder.

    This bench has historical duplicate trees (legacy vs module tree). Desk may call `check_pending_migration()`
    which expects the standard JSON file to exist under the module path. If it's missing, opening a DocType
    document crashes with FileNotFoundError.

    We export only when the file is missing to keep the patch idempotent and avoid rewriting files unnecessarily.
    """

    module = frappe.scrub("Ferum Custom")
    doctypes = frappe.get_all("DocType", filters={"module": "Ferum Custom", "custom": 0}, pluck="name")

    for dt in doctypes:
        try:
            path = Path(get_file_path(module, "DocType", dt))
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Failed to resolve doctype file path: {dt}")
            continue

        if path.exists():
            continue

        try:
            frappe.get_doc("DocType", dt).export_doc()
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Failed to export DocType file: {dt}")
