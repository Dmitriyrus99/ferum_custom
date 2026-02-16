from __future__ import annotations

"""Patch skeleton (idempotent, safe-by-default).

Usage:
- add dotted path to `ferum_custom/patches.txt` under the correct stage
- run `bench --site <site> migrate`

Rules:
- never print or return secrets
- always guard on DocType/field existence
- keep the patch idempotent (re-running should not duplicate/mis-migrate)
- prefer bounded batches and log summary (not payload)
"""

from collections.abc import Iterable

import frappe


def _chunks(values: list[str], size: int = 500) -> Iterable[list[str]]:
	for i in range(0, len(values), size):
		yield values[i : i + size]


def execute() -> None:
	# 1) Early exit if app / doctypes are not installed yet.
	if not frappe.db.exists("DocType", "Target DocType"):
		return

	# 2) Guard on schema expectations (columns/custom fields).
	if not frappe.db.has_column("Target DocType", "some_field"):
		return

	# 3) Bounded read -> compute -> write.
	#    Prefer `frappe.get_all(..., pluck='name', limit_page_length=...)` and process in chunks.
	names = frappe.get_all("Target DocType", pluck="name", limit_page_length=200000)
	if not names:
		return

	updated = 0
	for batch in _chunks([str(n).strip() for n in names if n], size=500):
		# Example: set missing defaults without overwriting user edits.
		for name in batch:
			current = frappe.db.get_value("Target DocType", name, "some_field")
			if current:
				continue
			frappe.db.set_value("Target DocType", name, "some_field", "default", update_modified=False)
			updated += 1

	if updated:
		frappe.db.commit()
		frappe.clear_cache()
		frappe.log_error(title="Patch: target_doctype_backfill", message=f"updated={updated}")
