from __future__ import annotations

import frappe


def _user_permissions(user: str, allow: str) -> set[str]:
	if not frappe.db.exists("DocType", "User Permission"):
		return set()
	rows = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": allow},
		pluck="for_value",
		limit=2000,
	)
	return {str(v) for v in rows if v}


def _customers_from_contact_user(user: str) -> set[str]:
	"""Resolve Customer list from Contact.user -> Contact.links (Dynamic Link)."""
	if not frappe.db.exists("DocType", "Contact") or not frappe.db.exists("DocType", "Dynamic Link"):
		return set()
	contacts = frappe.get_all("Contact", filters={"user": user}, pluck="name", limit=200)
	if not contacts:
		return set()
	customers = frappe.get_all(
		"Dynamic Link",
		filters={
			"parenttype": "Contact",
			"parent": ["in", list(contacts)],
			"link_doctype": "Customer",
		},
		pluck="link_name",
		limit=500,
	)
	return {str(c) for c in customers if c}


def user_has_project_access(*, user: str, project: str) -> bool:
	"""Checks if user is allowed to access a Project (for Desk + bot + API scoping).

	Rules (minimal, consistent with Telegram access):
	- System Manager / Administrator: full access
	- Project.project_manager == user
	- Project.users child table contains user
	- Project Site.default_engineer == user
	- User Permission: Project
	- User Permission: Customer or Contact.user -> Customer, then Project.customer in that set
	"""

	user = str(user or "").strip()
	project = str(project or "").strip()
	if not user or not project:
		return False
	if user == "Administrator":
		return True

	try:
		roles = set(frappe.get_roles(user) or [])
	except Exception:
		roles = set()
	if "System Manager" in roles:
		return True

	if not frappe.db.exists("Project", project):
		return False

	project_meta = frappe.get_meta("Project")

	if project_meta.has_field("project_manager"):
		pm = frappe.db.get_value("Project", project, "project_manager")
		if str(pm or "").strip() == user:
			return True

	# Standard Project users child table
	if project_meta.has_field("users") and frappe.db.exists("DocType", "Project User"):
		if frappe.db.has_column("Project User", "user") and frappe.db.exists(
			"Project User",
			{"parenttype": "Project", "parent": project, "user": user},
		):
			return True

	# Engineer access via Project Site.default_engineer
	if frappe.db.exists("DocType", "Project Site") and frappe.db.has_column(
		"Project Site", "default_engineer"
	):
		rows = frappe.db.sql(
			"""
            select 1
            from `tabProject Site`
            where parenttype = 'Project'
              and parent = %(project)s
              and ifnull(default_engineer,'') = %(user)s
            limit 1
            """,
			{"project": project, "user": user},
		)
		if rows:
			return True

	if frappe.db.exists("DocType", "User Permission"):
		if frappe.db.exists("User Permission", {"user": user, "allow": "Project", "for_value": project}):
			return True

		customers = _user_permissions(user, "Customer")
		customers.update(_customers_from_contact_user(user))
		if customers and project_meta.has_field("customer"):
			customer = frappe.db.get_value("Project", project, "customer")
			if customer and str(customer) in customers:
				return True

	return False


def user_has_global_project_access(user: str) -> bool:
	user = str(user or "").strip()
	if not user or user == "Administrator":
		return True
	try:
		roles = set(frappe.get_roles(user) or [])
	except Exception:
		roles = set()
	return "System Manager" in roles


def projects_for_user(user: str) -> set[str]:
	"""Return list of Project names accessible to user (non-global users)."""
	user = str(user or "").strip()
	if not user or user_has_global_project_access(user):
		return set()

	if not frappe.db.exists("DocType", "Project"):
		return set()

	project_meta = frappe.get_meta("Project")
	projects: set[str] = set()

	if project_meta.has_field("project_manager"):
		projects.update(
			frappe.get_all(
				"Project",
				filters={"project_manager": user},
				pluck="name",
				limit=500,
			)
		)

	if project_meta.has_field("users") and frappe.db.exists("DocType", "Project User"):
		if frappe.db.has_column("Project User", "user"):
			projects.update(
				frappe.get_all(
					"Project User",
					filters={"parenttype": "Project", "user": user},
					pluck="parent",
					limit=500,
				)
			)

	if frappe.db.exists("DocType", "Project Site") and frappe.db.has_column(
		"Project Site", "default_engineer"
	):
		rows = frappe.db.sql(
			"""
            select distinct parent
            from `tabProject Site`
            where parenttype = 'Project'
              and ifnull(default_engineer,'') = %(user)s
            limit 500
            """,
			{"user": user},
		)
		projects.update({str(r[0]) for r in rows if r and r[0]})

	projects.update(_user_permissions(user, "Project"))

	customers = _user_permissions(user, "Customer")
	customers.update(_customers_from_contact_user(user))
	if customers and project_meta.has_field("customer"):
		projects.update(
			frappe.get_all(
				"Project",
				filters={"customer": ["in", list(customers)]},
				pluck="name",
				limit=500,
			)
		)

	return {p for p in projects if p}
