from __future__ import annotations

import json

import frappe


def _set_child_table(doc, fieldname: str, rows: list[dict]) -> None:
	doc.set(fieldname, [])
	for row in rows:
		doc.append(fieldname, row)


def _upsert_workspace(
	name: str,
	*,
	title: str,
	module: str = "Ferum Custom",
	icon: str | None = None,
	is_hidden: int = 0,
	roles: list[str] | None = None,
	shortcuts: list[dict] | None = None,
	content_blocks: list[dict] | None = None,
) -> None:
	if frappe.db.exists("Workspace", name):
		ws = frappe.get_doc("Workspace", name)
	else:
		ws = frappe.new_doc("Workspace")
		ws.name = name
		ws.title = title
		ws.label = title
		ws.module = module

	ws.title = title
	ws.label = title
	ws.module = module
	ws.icon = icon
	ws.is_hidden = int(is_hidden or 0)
	ws.public = 1

	if roles is not None:
		_set_child_table(ws, "roles", [{"role": r} for r in roles if (r or "").strip()])

	if shortcuts is not None:
		_set_child_table(ws, "shortcuts", shortcuts)

	if content_blocks is not None:
		ws.content = json.dumps(content_blocks, ensure_ascii=False)

	if ws.is_new():
		ws.insert(ignore_permissions=True)
	else:
		ws.save(ignore_permissions=True)


def _hide_workspace(name: str) -> None:
	if not frappe.db.exists("Workspace", name):
		return
	ws = frappe.get_doc("Workspace", name)
	changed = False
	if not int(ws.is_hidden or 0):
		ws.is_hidden = 1
		changed = True
	# Keep it restricted to System Manager if it ever becomes visible.
	if ws.roles:
		ws.set("roles", [])
		ws.append("roles", {"role": "System Manager"})
		changed = True
	if changed:
		ws.flags.ignore_links = True
		ws.save(ignore_permissions=True)


def _restrict_non_ferum_workspaces_to_sys_manager() -> None:
	for row in frappe.get_all("Workspace", fields=["name", "module"]):
		if (row.get("module") or "").strip() == "Ferum Custom":
			continue

		ws = frappe.get_doc("Workspace", row["name"])
		current_roles = {r.role for r in ws.roles}
		if current_roles == {"System Manager"}:
			continue

		ws.set("roles", [])
		ws.append("roles", {"role": "System Manager"})
		ws.flags.ignore_links = True
		ws.save(ignore_permissions=True)


def _ensure_user_role(user: str, role: str) -> None:
	if not user or not role:
		return
	if not frappe.db.exists("User", user) or not frappe.db.exists("Role", role):
		return
	doc = frappe.get_doc("User", user)
	if role in [r.role for r in doc.roles]:
		return
	doc.add_roles(role)
	doc.save(ignore_permissions=True)


def _set_default_workspace_for_role(*, role: str, workspace: str) -> None:
	if not role or not workspace:
		return
	if not frappe.db.exists("Role", role) or not frappe.db.exists("Workspace", workspace):
		return

	users = frappe.db.sql(
		"""
		select u.name
		from `tabUser` u
		inner join `tabHas Role` r on r.parent = u.name
		where r.parenttype = 'User'
		  and r.role = %(role)s
		  and u.enabled = 1
		  and u.user_type = 'System User'
		""",
		{"role": role},
	)
	for (user,) in users:
		doc = frappe.get_doc("User", user)
		if (doc.default_workspace or "").strip():
			continue
		doc.default_workspace = workspace
		doc.save(ignore_permissions=True)


def execute() -> None:
	# Role-specific minimal workspaces aligned with the P0 process and Telegram bot.
	_upsert_workspace(
		"Тендер",
		title="Тендер",
		roles=["Ferum Tender Specialist"],
		shortcuts=[
			{"label": "Проекты", "type": "DocType", "link_to": "Project", "doc_view": "List"},
			{"label": "Новый проект", "type": "URL", "url": "/app/project/new"},
			{"label": "Мои задачи", "type": "DocType", "link_to": "ToDo", "doc_view": "List"},
		],
		content_blocks=[
			{"type": "header", "data": {"text": "Тендер", "col": 12}},
			{"type": "shortcut", "data": {"shortcut_name": "Проекты", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Новый проект", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Мои задачи", "col": 3}},
		],
	)

	_upsert_workspace(
		"Менеджер проекта",
		title="Менеджер проекта",
		roles=["Project Manager"],
		shortcuts=[
			{"label": "Проекты", "type": "DocType", "link_to": "Project", "doc_view": "List"},
			{"label": "Заявки", "type": "DocType", "link_to": "Service Request", "doc_view": "List"},
			{"label": "Новая заявка", "type": "URL", "url": "/app/service-request/new"},
			{"label": "Без инженера", "type": "Report", "link_to": "Unassigned Service Requests"},
			{
				"label": "Открытые по инженерам",
				"type": "Report",
				"link_to": "Open Service Requests by Engineer",
			},
			{"label": "Мои задачи", "type": "DocType", "link_to": "ToDo", "doc_view": "List"},
		],
		content_blocks=[
			{"type": "header", "data": {"text": "Менеджер проекта", "col": 12}},
			{"type": "shortcut", "data": {"shortcut_name": "Проекты", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Заявки", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Новая заявка", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Без инженера", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Открытые по инженерам", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Мои задачи", "col": 3}},
		],
	)

	_upsert_workspace(
		"Операционный менеджер",
		title="Офис-менеджер",
		roles=["Ferum Office Manager", "Office Manager"],
		shortcuts=[
			{"label": "Проекты", "type": "DocType", "link_to": "Project", "doc_view": "List"},
			{"label": "Заявки", "type": "DocType", "link_to": "Service Request", "doc_view": "List"},
			{"label": "Без инженера", "type": "Report", "link_to": "Unassigned Service Requests"},
			{"label": "Мои задачи", "type": "DocType", "link_to": "ToDo", "doc_view": "List"},
		],
		content_blocks=[
			{"type": "header", "data": {"text": "Офис-менеджер", "col": 12}},
			{"type": "shortcut", "data": {"shortcut_name": "Проекты", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Заявки", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Без инженера", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Мои задачи", "col": 3}},
		],
	)

	_upsert_workspace(
		"Инженер",
		title="Инженер",
		roles=["Service Engineer"],
		shortcuts=[
			{"label": "Заявки", "type": "DocType", "link_to": "Service Request", "doc_view": "List"},
			{"label": "Проекты", "type": "DocType", "link_to": "Project", "doc_view": "List"},
			{"label": "Мои задачи", "type": "DocType", "link_to": "ToDo", "doc_view": "List"},
		],
		content_blocks=[
			{"type": "header", "data": {"text": "Инженер", "col": 12}},
			{"type": "shortcut", "data": {"shortcut_name": "Заявки", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Проекты", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Мои задачи", "col": 3}},
		],
	)

	_upsert_workspace(
		"Директор",
		title="Директор",
		roles=["Ferum Director", "General Director"],
		shortcuts=[
			{"label": "Проекты", "type": "DocType", "link_to": "Project", "doc_view": "List"},
			{"label": "Заявки", "type": "DocType", "link_to": "Service Request", "doc_view": "List"},
			{"label": "Без инженера", "type": "Report", "link_to": "Unassigned Service Requests"},
			{
				"label": "Открытые по инженерам",
				"type": "Report",
				"link_to": "Open Service Requests by Engineer",
			},
			{"label": "Мои задачи", "type": "DocType", "link_to": "ToDo", "doc_view": "List"},
		],
		content_blocks=[
			{"type": "header", "data": {"text": "Директор", "col": 12}},
			{"type": "shortcut", "data": {"shortcut_name": "Проекты", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Заявки", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Без инженера", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Открытые по инженерам", "col": 3}},
			{"type": "shortcut", "data": {"shortcut_name": "Мои задачи", "col": 3}},
		],
	)

	# Hide legacy/overlapping Ferum workspaces to keep UX minimal.
	for legacy_ws in (
		"Управление проектами",
		"Сервисные операции",
		"Регламентное обслуживание",
		"Руководитель отдела",
	):
		_hide_workspace(legacy_ws)

	# Restrict ERPNext default workspaces so non-admin roles only see Ferum pages.
	_restrict_non_ferum_workspaces_to_sys_manager()

	# Ensure known director user has the Ferum Director role.
	_ensure_user_role("rusakov@ferumrus.ru", "Ferum Director")

	# Set default workspace for users, only when not already configured.
	_set_default_workspace_for_role(role="Ferum Director", workspace="Директор")
	_set_default_workspace_for_role(role="General Director", workspace="Директор")
	_set_default_workspace_for_role(role="Ferum Tender Specialist", workspace="Тендер")
	_set_default_workspace_for_role(role="Ferum Office Manager", workspace="Операционный менеджер")
	_set_default_workspace_for_role(role="Project Manager", workspace="Менеджер проекта")
	_set_default_workspace_for_role(role="Service Engineer", workspace="Инженер")

	frappe.clear_cache()
