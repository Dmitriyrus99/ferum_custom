from __future__ import annotations

from typing import Any

import frappe

from ferum_custom.security.project_access import projects_for_user, user_has_global_project_access
from ferum_custom.utils import project_sites


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

	truth_dt = project_sites.truth_doctype()
	row_dt = project_sites.legacy_row_doctype()
	use_truth = bool(
		project_sites.is_truth_enabled()
		and frappe.db.exists("DocType", truth_dt)
		and frappe.db.has_column(truth_dt, "project")
	)

	conditions: list[str] = []
	values: list[Any] = []

	if project:
		conditions.append("ps.project = %s" if use_truth else "ps.parent = %s")
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
		conditions.append(f"{'ps.project' if use_truth else 'ps.parent'} in ({placeholders})")
		values.extend(allowed)

	if use_truth:
		conditions.append("ifnull(ps.project, '') != ''")
	else:
		conditions.append("ps.parenttype = 'Project'")
		conditions.append("ps.parentfield = 'project_sites'")

	where = f"where {' and '.join(conditions)}" if conditions else ""

	if not use_truth:
		table_dt = row_dt or "Project Site"
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
			from `tab{table_dt}` ps
			left join `tabProject` p on p.name = ps.parent
			{where}
			order by p.modified desc, ps.idx asc
			limit 2000
			""",
			values,
			as_list=True,
		)
		return columns, rows

	rows = frappe.db.sql(
		f"""
		select
			ps.project as project,
			coalesce(ps.customer, p.customer) as customer,
			ps.site_name as site_name,
			ps.address as address,
			ps.default_engineer as engineer,
			ps.drive_folder_url as drive_folder_url,
			ps.modified as modified
		from `tabProject Site` ps
		left join `tabProject` p on p.name = ps.project
		{where}
		order by ps.modified desc
		limit 2000
		""",
		values,
		as_list=True,
	)

	return columns, rows
