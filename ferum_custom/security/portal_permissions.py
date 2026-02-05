from __future__ import annotations

import frappe


def _has_client_role(user: str) -> bool:
	return "Client" in frappe.get_roles(user)


def contract_permission_query_conditions(user: str) -> str:
	"""Hide contracts from portal/telegram without removing permissions."""
	if not user or user == "Administrator":
		return ""
	if not _has_client_role(user):
		return ""

	# Additional visibility flag on top of User Permission filtering.
	if frappe.db.has_column("Contract", "is_portal_visible"):
		return "`tabContract`.`is_portal_visible` = 1"
	return ""


def sales_invoice_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	"""Portal clients must not access financial documents."""
	user = user or frappe.session.user
	if not user or user == "Administrator":
		return None
	if _has_client_role(user):
		return False

	# Fallback to default permission evaluation.
	return None


def service_act_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	"""Extra safety: even if permissions are misconfigured, deny clients."""
	user = user or frappe.session.user
	if not user or user == "Administrator":
		return None
	if _has_client_role(user):
		return False
	return None


def invoice_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	"""Custom Invoice is a financial document: deny for portal clients."""
	user = user or frappe.session.user
	if not user or user == "Administrator":
		return None
	if _has_client_role(user):
		return False
	return None
