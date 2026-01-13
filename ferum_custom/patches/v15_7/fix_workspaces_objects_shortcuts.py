from __future__ import annotations

import json
from typing import Any

import frappe


def _rebuild_workspace_content(workspace_doc) -> None:
	title = workspace_doc.title or workspace_doc.name

	blocks: list[dict[str, Any]] = [
		{"type": "header", "data": {"text": title, "col": 12}},
	]

	shortcuts = list(workspace_doc.get("shortcuts") or [])
	shortcuts.sort(key=lambda r: int(getattr(r, "idx", 0) or 0))

	for row in shortcuts:
		label = (getattr(row, "label", None) or "").strip()
		if not label:
			continue
		col = 4 if (getattr(row, "type", "") == "Report") else 3
		blocks.append({"type": "shortcut", "data": {"shortcut_name": label, "col": col}})

	workspace_doc.content = json.dumps(blocks, ensure_ascii=False, separators=(",", ":"))


def _should_convert_to_service_object(row) -> bool:
	label = (getattr(row, "label", None) or "").strip()
	link_to = getattr(row, "link_to", None)
	url = getattr(row, "url", None) or ""

	if label.startswith("Объекты"):
		return True

	if link_to == "Asset" and label == "Объекты":
		return True

	if "/app/asset" in url and label.startswith("Объекты"):
		return True

	return False


def execute():
	workspaces = frappe.get_all("Workspace", filters={"module": "Ferum Custom"}, pluck="name")

	for name in workspaces:
		ws = frappe.get_doc("Workspace", name)
		changed = False

		for row in ws.get("shortcuts") or []:
			if not _should_convert_to_service_object(row):
				continue

			# Unify all "Objects" shortcuts to Service Object list
			row.label = "Объекты"
			row.type = "DocType"
			row.link_to = "Service Object"
			row.url = ""
			row.doc_view = "List"
			changed = True

		if changed:
			_rebuild_workspace_content(ws)
			ws.flags.ignore_links = True
			ws.save(ignore_permissions=True)
