from __future__ import annotations

import frappe

from ferum_custom.security.project_access import (
	projects_for_user,
	user_has_global_project_access,
	user_has_project_access,
)


def _escaped_in(values: list[str]) -> str:
	return ", ".join(frappe.db.escape(v) for v in values)


def project_site_permission_query_conditions(user: str) -> str:
	"""Restrict Project Site list/link queries by Project access."""
	user = str(user or "").strip()
	if not user or user_has_global_project_access(user):
		return ""

	allowed = sorted(projects_for_user(user))
	if not allowed:
		return "1=0"

	# Prefer truth model.
	if frappe.db.exists("DocType", "Project Site") and frappe.db.has_column("Project Site", "project"):
		projects_sql = _escaped_in(allowed)
		return f"`tabProject Site`.`project` in ({projects_sql})"

	return "1=0"


def service_logbook_permission_query_conditions(user: str) -> str:
	user = str(user or "").strip()
	if not user or user_has_global_project_access(user):
		return ""

	allowed = sorted(projects_for_user(user))
	if not allowed:
		return "1=0"

	projects_sql = _escaped_in(allowed)
	return (
		"`tabService Logbook`.`project_site` in ("
		"select `tabProject Site`.`name` from `tabProject Site` "
		f"where `tabProject Site`.`project` in ({projects_sql})"
		")"
	)


def service_log_entry_permission_query_conditions(user: str) -> str:
	user = str(user or "").strip()
	if not user or user_has_global_project_access(user):
		return ""

	allowed = sorted(projects_for_user(user))
	if not allowed:
		return "1=0"

	projects_sql = _escaped_in(allowed)
	return (
		"`tabService Log Entry`.`project_site` in ("
		"select `tabProject Site`.`name` from `tabProject Site` "
		f"where `tabProject Site`.`project` in ({projects_sql})"
		")"
	)


def project_site_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	user = str(user or frappe.session.user or "").strip()
	if not user or user == "Administrator":
		return None
	if not doc:
		return False

	try:
		project = str(doc.project or "").strip()
	except Exception:
		project = ""
	if project:
		return user_has_project_access(user=user, project=project)

	# If project is not set yet, fall back to global roles.
	return True if user_has_global_project_access(user) else False


def _project_site_from_logbook(name: str) -> str | None:
	val = frappe.db.get_value("Service Logbook", name, "project_site")
	val = str(val or "").strip()
	return val or None


def _project_from_site(site: str) -> str | None:
	val = frappe.db.get_value("Project Site", site, "project")
	val = str(val or "").strip()
	return val or None


def service_logbook_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	user = str(user or frappe.session.user or "").strip()
	if not user or user == "Administrator":
		return None
	if not doc:
		return False

	try:
		site = str(doc.project_site or "").strip()
	except Exception:
		site = ""
	if not site:
		return True if user_has_global_project_access(user) else False

	project = _project_from_site(site)
	if not project:
		return True if user_has_global_project_access(user) else False

	return user_has_project_access(user=user, project=project)


def service_log_entry_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	user = str(user or frappe.session.user or "").strip()
	if not user or user == "Administrator":
		return None
	if not doc:
		return False

	# Prefer explicit project_site on entry.
	try:
		site = str(doc.project_site or "").strip()
	except Exception:
		site = ""
	try:
		logbook = doc.logbook
	except Exception:
		logbook = None
	if not site and logbook:
		site = _project_site_from_logbook(str(logbook or "")) or ""
	if not site:
		return True if user_has_global_project_access(user) else False

	project = _project_from_site(site)
	if not project:
		return True if user_has_global_project_access(user) else False

	return user_has_project_access(user=user, project=project)
