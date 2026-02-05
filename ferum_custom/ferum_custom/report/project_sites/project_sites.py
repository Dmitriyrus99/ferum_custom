from __future__ import annotations

from typing import Any

import frappe

from ferum_custom.security.project_access import projects_for_user, user_has_global_project_access


def execute(filters: dict | None = None) -> tuple[list[str], list[list[Any]]]:
	filters = filters or {}
	project = str(filters.get("project") or "").strip()
	engineer = str(filters.get("engineer") or "").strip()

	columns = [
		"Проект:Link/Project:180",
		"Клиент:Link/Customer:180",
		"Объект:Data:220",
		"Адрес:Data:240",
		"Инженер:Link/User:180",
		"Папка Google Drive:Data:220",
		"Изменен:Datetime:160",
	]

	conditions: list[str] = [
		"ps.parenttype = 'Project'",
		"ps.parentfield = 'project_sites'",
	]
	values: list[Any] = []

	if project:
		conditions.append("ps.parent = %s")
		values.append(project)
	if engineer:
		conditions.append("ifnull(ps.default_engineer, '') = %s")
		values.append(engineer)

	user = frappe.session.user
	if not user_has_global_project_access(user):
		allowed = sorted(projects_for_user(user))
		if not allowed:
			return columns, []
		placeholders = ", ".join(["%s"] * len(allowed))
		conditions.append(f"ps.parent in ({placeholders})")
		values.extend(allowed)

	where = f"where {' and '.join(conditions)}" if conditions else ""

	rows = frappe.db.sql(
		f"""
		select
			ps.parent as project,
			p.customer as customer,
			ps.site_name as site_name,
			ps.address as address,
			ps.default_engineer as engineer,
			ps.drive_folder_url as drive_folder_url,
			ps.modified as modified
		from `tabProject Site` ps
		left join `tabProject` p on p.name = ps.parent
		{where}
		order by p.modified desc, ps.idx asc
		limit 2000
		""",
		values,
		as_list=True,
	)

	return columns, rows
