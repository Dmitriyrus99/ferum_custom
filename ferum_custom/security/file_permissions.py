from __future__ import annotations

import frappe

from ferum_custom.security.project_access import (
	projects_for_user,
	user_has_global_project_access,
	user_has_project_access,
)
from ferum_custom.services.project_documents_config import (
	ATTACHED_TO_FIELD,
	CLIENT_ALLOWED_TYPES,
	UPLOAD_ROLES,
)


def _is_ferum_project_document(doc) -> bool:
	if not doc:
		return False
	attached_to_doctype = str(getattr(doc, "attached_to_doctype", "") or "").strip()
	attached_to_field = str(getattr(doc, "attached_to_field", "") or "").strip()
	if attached_to_doctype != "Project":
		return False
	if attached_to_field != ATTACHED_TO_FIELD:
		return False
	return True


def _is_client_user(user: str) -> bool:
	try:
		return "Client" in set(frappe.get_roles(user) or [])
	except Exception:
		return False


def file_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	"""Restrict access to Ferum Project documents stored in File.

	Important: return None for non-Ferum files to avoid breaking standard attachments.
	"""

	user = user or frappe.session.user
	if not user or user == "Administrator":
		return None

	if not _is_ferum_project_document(doc):
		return None

	project = str(getattr(doc, "attached_to_name", "") or "").strip()
	if not project:
		return False

	if not user_has_project_access(user=user, project=project):
		return False

	if _is_client_user(user):
		doc_type = str(getattr(doc, "ferum_doc_type", "") or "").strip()
		if doc_type not in CLIENT_ALLOWED_TYPES:
			return False

	if ptype in {"write", "delete", "submit", "cancel", "amend"}:
		try:
			roles = set(frappe.get_roles(user) or [])
		except Exception:
			roles = set()
		if "System Manager" in roles:
			return True
		if roles.intersection(UPLOAD_ROLES):
			return True
		return False

	return True


def file_permission_query_conditions(user: str) -> str:
	"""SQL conditions for File lists (applies only to Ferum project documents)."""

	user = str(user or "").strip()
	if not user or user_has_global_project_access(user):
		return ""

	allowed_projects = sorted(projects_for_user(user))
	if not allowed_projects:
		return (
			"(ifnull(`tabFile`.`attached_to_doctype`, '') != 'Project' "
			"or ifnull(`tabFile`.`attached_to_field`, '') != 'ferum_project_documents')"
		)

	project_sql = ", ".join(frappe.db.escape(p) for p in allowed_projects)
	not_ferum = (
		"(ifnull(`tabFile`.`attached_to_doctype`, '') != 'Project' "
		"or ifnull(`tabFile`.`attached_to_field`, '') != 'ferum_project_documents')"
	)

	ferum_allowed = f"(`tabFile`.`attached_to_name` in ({project_sql}))"
	if _is_client_user(user):
		types_sql = ", ".join(frappe.db.escape(t) for t in sorted(CLIENT_ALLOWED_TYPES))
		ferum_allowed = f"({ferum_allowed} and ifnull(`tabFile`.`ferum_doc_type`, '') in ({types_sql}))"

	return f"({not_ferum} or {ferum_allowed})"
