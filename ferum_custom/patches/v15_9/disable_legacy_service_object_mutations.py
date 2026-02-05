from __future__ import annotations

import frappe


def execute() -> None:
	"""Disable legacy Service Object mutations (idempotent).

	We keep the DocType for historical references, but prevent non-admin roles from mutating it.
	"""
	dt = "Service Object" if frappe.db.exists("DocType", "Service Object") else "ServiceObject"
	if not frappe.db.exists("DocType", dt):
		return

	perms = frappe.get_all(
		"DocPerm",
		filters={"parent": dt, "parenttype": "DocType"},
		fields=["name", "role"],
	)
	for p in perms:
		if p.role in {"Administrator", "System Manager"}:
			continue
		frappe.db.set_value(
			"DocPerm",
			p.name,
			{
				"create": 0,
				"write": 0,
				"delete": 0,
				"submit": 0,
				"cancel": 0,
				"amend": 0,
			},
			update_modified=False,
		)

	frappe.clear_cache()
