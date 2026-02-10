from __future__ import annotations

import frappe


def _project_sites_child_doctype() -> str | None:
	"""Return legacy child doctype used by Project.project_sites (Table)."""
	if frappe.db.exists("DocType", "Project Site Row"):
		return "Project Site Row"
	if frappe.db.exists("DocType", "Project Site"):
		try:
			dt = frappe.get_doc("DocType", "Project Site")
			if int(getattr(dt, "istable", 0) or 0) == 1:
				return "Project Site"
		except Exception:
			return None
	return None


def _insert_project_site(
	*,
	project: str,
	idx: int,
	site_name: str,
	address: str,
	default_engineer: str | None,
	notes: str,
) -> None:
	# Insert directly into child table to avoid triggering Project validate hooks (P0 gates).
	child_dt = _project_sites_child_doctype()
	if not child_dt:
		return
	doc = frappe.get_doc(
		{
			"doctype": child_dt,
			"parenttype": "Project",
			"parent": project,
			"parentfield": "project_sites",
			"idx": int(idx),
			"site_name": site_name,
			"address": address,
			"default_engineer": default_engineer,
			"notes": notes,
		}
	)
	doc.insert(ignore_permissions=True)


def execute() -> None:
	"""Backfill Project Sites (child rows) for migrated Projects.

	Mapping strategy (legacy -> new):
	- Service Object.project points to Service Project (legacy)
	- Contract.contract_code stores legacy Service Project name
	- Project.contract links to Contract
	=> Project Sites are created for Projects with a Contract whose contract_code matches a Service Project name.
	"""
	if not frappe.db.exists("DocType", "Project"):
		return
	child_dt = _project_sites_child_doctype()
	if not child_dt:
		return
	if not frappe.get_meta("Project").has_field("project_sites"):
		return
	if not frappe.db.exists("DocType", "Contract"):
		return
	if not frappe.db.exists("DocType", "Service Project"):
		return
	if not frappe.db.exists("DocType", "Service Object"):
		return

	projects = frappe.get_all("Project", fields=["name", "contract"], limit=5000)
	for p in projects:
		project_name = p.get("name")
		contract = (p.get("contract") or "").strip()
		if not project_name or not contract:
			continue

		# Skip if already has at least 1 Project Site.
		if frappe.get_all(child_dt, filters={"parenttype": "Project", "parent": project_name}, limit=1):
			continue

		legacy_service_project = frappe.db.get_value("Contract", contract, "contract_code")
		legacy_service_project = (legacy_service_project or "").strip()
		if not legacy_service_project or not frappe.db.exists("Service Project", legacy_service_project):
			continue

		service_objects = frappe.get_all(
			"Service Object",
			filters={"project": legacy_service_project},
			fields=["name", "object_name", "address", "default_engineer"],
			limit_page_length=500,
		)
		if not service_objects:
			continue

		for idx, so in enumerate(service_objects, start=1):
			address = (so.get("address") or "").strip() or "Адрес уточняется"
			site_name = (so.get("object_name") or so.get("name") or "").strip()
			if not site_name:
				site_name = "Объект"
			try:
				_insert_project_site(
					project=project_name,
					idx=idx,
					site_name=site_name,
					address=address,
					default_engineer=so.get("default_engineer"),
					notes=f"legacy_service_object={so.get('name')}",
				)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Backfill Project Sites failed")

	frappe.clear_cache()
