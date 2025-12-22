from __future__ import annotations

import json
from typing import Any

import frappe


def _rebuild_workspace_content(workspace_doc) -> bool:
    title = workspace_doc.title or workspace_doc.name

    new_blocks: list[dict[str, Any]] = [
        {"type": "header", "data": {"text": title, "col": 12}},
    ]

    shortcuts = list(workspace_doc.get("shortcuts") or [])
    shortcuts.sort(key=lambda r: int(getattr(r, "idx", 0) or 0))

    for row in shortcuts:
        label = (getattr(row, "label", None) or "").strip()
        if not label:
            continue
        col = 4 if (getattr(row, "type", "") == "Report") else 3
        new_blocks.append({"type": "shortcut", "data": {"shortcut_name": label, "col": col}})

    try:
        current = json.loads(workspace_doc.content or "[]")
    except Exception:
        current = None

    if current == new_blocks:
        return False

    workspace_doc.content = json.dumps(new_blocks, ensure_ascii=False, separators=(",", ":"))
    return True


def _fix_report_shortcut_targets(workspace_doc) -> bool:
    """Fix historical shortcut targets that referenced non-existent core reports."""

    changed = False

    replacements = {
        "Unassigned Issues": "Unassigned Service Requests",
        "Open Issues by Engineer": "Open Service Requests by Engineer",
    }

    for row in workspace_doc.get("shortcuts") or []:
        if getattr(row, "type", "") != "Report":
            continue

        target = getattr(row, "link_to", None)
        if target not in replacements:
            continue

        new_target = replacements[target]
        if frappe.db.exists("Report", new_target):
            row.link_to = new_target
            changed = True

    return changed


def execute():
    workspaces = frappe.get_all("Workspace", filters={"module": "Ferum Custom"}, pluck="name")

    for name in workspaces:
        ws = frappe.get_doc("Workspace", name)

        shortcut_changed = _fix_report_shortcut_targets(ws)
        content_changed = _rebuild_workspace_content(ws)

        if shortcut_changed or content_changed:
            ws.save(ignore_permissions=True)
