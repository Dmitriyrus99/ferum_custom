from __future__ import annotations

import json
from typing import Any

import frappe

REPORT_NAME = "Project Sites"

# Known Ferum workspaces (created/managed by patches).
TARGET_WORKSPACES: tuple[str, ...] = (
	"Тендер",
	"Менеджер проекта",
	"Операционный менеджер",
	"Инженер",
	"Директор",
	"Управление проектами",
	"Сервисные операции",
	"Регламентное обслуживание",
)


def _ensure_objects_shortcut(ws) -> bool:
	"""Ensure the workspace has an 'Объекты' shortcut pointing to the report."""
	changed = False

	# Convert existing object-like shortcuts to the report.
	for row in ws.get("shortcuts") or []:
		label = str(getattr(row, "label", "") or "").strip()
		if not label.startswith("Объекты"):
			continue
		if getattr(row, "type", "") == "Report" and getattr(row, "link_to", None) == REPORT_NAME:
			continue
		row.type = "Report"
		row.link_to = REPORT_NAME
		row.url = ""
		if hasattr(row, "doc_view"):
			row.doc_view = ""
		changed = True

	# If there is no explicit 'Объекты' shortcut, add it (for new minimal workspaces).
	if not any(str(getattr(r, "label", "") or "").strip() == "Объекты" for r in ws.get("shortcuts") or []):
		ws.append("shortcuts", {"label": "Объекты", "type": "Report", "link_to": REPORT_NAME})
		changed = True

	return changed


def _ensure_objects_block(ws) -> bool:
	"""Ensure workspace.content includes the 'Объекты' shortcut block (keeps existing layout)."""
	try:
		blocks = json.loads(ws.content or "[]")
	except Exception:
		return False

	if not isinstance(blocks, list):
		return False

	for b in blocks:
		if not isinstance(b, dict):
			continue
		if b.get("type") != "shortcut":
			continue
		data = b.get("data")
		if isinstance(data, dict) and data.get("shortcut_name") == "Объекты":
			return False

	# Insert after "Проекты" if present, else right after the header.
	insert_at = 0
	for i, b in enumerate(blocks):
		if not isinstance(b, dict):
			continue
		if b.get("type") == "header":
			insert_at = i + 1
		if b.get("type") == "shortcut" and isinstance(b.get("data"), dict):
			if b["data"].get("shortcut_name") == "Проекты":
				insert_at = i + 1
				break

	blocks.insert(insert_at, {"type": "shortcut", "data": {"shortcut_name": "Объекты", "col": 3}})
	ws.content = json.dumps(blocks, ensure_ascii=False, separators=(",", ":"))
	return True


def _process_workspace(name: str) -> None:
	if not frappe.db.exists("Workspace", name):
		return
	ws = frappe.get_doc("Workspace", name)

	changed = False
	changed = _ensure_objects_shortcut(ws) or changed
	changed = _ensure_objects_block(ws) or changed

	if changed:
		ws.flags.ignore_links = True
		ws.save(ignore_permissions=True)


def execute() -> None:
	for name in TARGET_WORKSPACES:
		_process_workspace(name)

	# Also normalize within Ferum Custom module (safe scope).
	for name in frappe.get_all("Workspace", filters={"module": "Ferum Custom"}, pluck="name"):
		_process_workspace(name)

	frappe.clear_cache()
