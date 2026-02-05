from __future__ import annotations

import frappe

FERUM_DIRECTOR_ROLE = "Ferum Director"
FERUM_TENDER_SPECIALIST_ROLE = "Ferum Tender Specialist"
FERUM_OFFICE_MANAGER_ROLE = "Ferum Office Manager"

FERUM_DIRECTOR_ROLES = (FERUM_DIRECTOR_ROLE, "General Director")
FERUM_OFFICE_MANAGER_ROLES = (FERUM_OFFICE_MANAGER_ROLE, "Office Manager")
FERUM_TENDER_SPECIALIST_ROLES = (FERUM_TENDER_SPECIALIST_ROLE,)


def first_enabled_user_with_role(role: str) -> str | None:
	"""Return first enabled system user with the given role (best-effort).

	Order preference:
	- Most recently modified UserRole assignment (approx, via User.modified desc)
	- Excludes Administrator from normal resolution, but falls back to it when nothing else exists.
	"""
	if not role or not frappe.db.exists("Role", role):
		return None

	# Join via UserRole; then prefer enabled users.
	rows = frappe.db.sql(
		"""
		select ur.parent as user
		from `tabHas Role` ur
		inner join `tabUser` u on u.name = ur.parent
		where ur.role = %(role)s
		  and u.enabled = 1
		  and u.name != 'Administrator'
		order by u.modified desc
		limit 1
		""",
		{"role": role},
	)
	if rows and rows[0] and rows[0][0]:
		return str(rows[0][0])
	return None


def first_enabled_user_with_roles(roles: tuple[str, ...]) -> str | None:
	for role in roles or ():
		user = first_enabled_user_with_role(role)
		if user:
			return user
	return None


def enabled_users_with_role(role: str, *, limit: int = 50) -> list[str]:
	if not role or not frappe.db.exists("Role", role):
		return []
	rows = frappe.db.sql(
		"""
		select ur.parent as user
		from `tabHas Role` ur
		inner join `tabUser` u on u.name = ur.parent
		where ur.role = %(role)s
		  and u.enabled = 1
		order by u.modified desc
		limit %(limit)s
		""",
		{"role": role, "limit": int(limit)},
	)
	return [str(r[0]) for r in rows if r and r[0]]


def enabled_users_with_roles(roles: tuple[str, ...], *, limit: int = 50) -> list[str]:
	out: list[str] = []
	for role in roles or ():
		for user in enabled_users_with_role(role, limit=limit):
			if user not in out:
				out.append(user)
	return out
