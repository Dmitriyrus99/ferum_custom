from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from ferum_custom.utils import project_sites


def _require_authenticated() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
@frappe.read_only()
def list_objects(project: str | None = None, limit: int = 500, **kwargs: Any) -> dict:
	"""List project objects/sites.

	Compatibility API: older desk/portal code may call this module.
	"""
	_require_authenticated()

	project = (project or "").strip()
	if not project:
		frappe.throw(_("Missing project."), frappe.ValidationError)

	if not frappe.db.exists("Project", project):
		frappe.throw(_("Project not found."), frappe.ValidationError)

	if not frappe.has_permission("Project", doc=project, ptype="read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	limit = max(1, min(cint(limit) or 500, 1000))

	out: list[dict] = []
	rows = project_sites.list_sites_for_project(project=project, limit=limit)
	for r in rows:
		out.append(
			{
				"name": r.get("name"),
				"object_name": r.get("site_name"),
				"address": r.get("address"),
				"default_engineer": r.get("default_engineer"),
			}
		)

	return {"ok": True, "count": len(out), "items": out}


@frappe.whitelist()
@frappe.read_only()
def list_issues(project: str | None = None, limit: int = 20, **kwargs: Any) -> dict:
	"""List service requests (\"issues\") for desk/portal integrations."""
	_require_authenticated()

	limit = max(1, min(cint(limit) or 20, 200))
	project = (project or "").strip()

	filters: dict[str, object] = {}
	or_filters: list[dict[str, object]] = []
	if project:
		or_filters = [{"erp_project": project}, {"project": project}]

	rows = frappe.get_list(
		"Service Request",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"title",
			"status",
			"priority",
			"erp_project",
			"project_site",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=limit,
	)
	return {"ok": True, "count": len(rows), "items": rows}


@frappe.whitelist(methods=["POST"])
def create_issue(
	title: str | None = None,
	description: str | None = None,
	project: str | None = None,
	project_site: str | None = None,
	priority: str | None = None,
	**kwargs: Any,
) -> dict:
	"""Create a Service Request (compat endpoint)."""
	_require_authenticated()

	title = (title or "").strip()
	if not title:
		frappe.throw(_("Missing title."), frappe.ValidationError)

	doc = frappe.get_doc(
		{
			"doctype": "Service Request",
			"title": title,
			"description": (description or "").strip() or None,
		}
	)

	project = (project or "").strip()
	if project:
		if frappe.db.exists("Project", project):
			doc.erp_project = project
		elif frappe.db.exists("Service Project", project):
			doc.project = project
		else:
			frappe.throw(_("Project not found."), frappe.ValidationError)

	project_site = (project_site or "").strip()
	if project_site:
		doc.project_site = project_site

	priority = (priority or "").strip()
	if priority:
		doc.priority = priority

	doc.insert()
	return {"ok": True, "name": doc.name}
