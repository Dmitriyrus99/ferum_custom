from __future__ import annotations

import frappe


def execute():
	objects = frappe.get_all(
		"Service Object",
		filters={"project": ["!=", ""]},
		fields=["name", "project", "company", "customer", "default_engineer"],
	)
	if not objects:
		return

	project_names = sorted({o.project for o in objects if o.project})
	projects = frappe.get_all(
		"Service Project",
		filters={"name": ["in", project_names]},
		fields=["name", "company", "customer", "default_engineer"],
	)
	by_name = {p.name: p for p in projects}

	for o in objects:
		p = by_name.get(o.project)
		if not p:
			continue

		updates = {}
		if p.company and o.company != p.company:
			updates["company"] = p.company
		if p.customer and o.customer != p.customer:
			updates["customer"] = p.customer
		if not o.default_engineer and p.default_engineer:
			updates["default_engineer"] = p.default_engineer

		if updates:
			frappe.db.set_value("Service Object", o.name, updates, update_modified=False)

