from __future__ import annotations

import json
import os
from typing import Any

import frappe


def _load_json(path: str) -> Any:
	with open(path, encoding="utf-8") as f:
		return json.load(f)


def _install_doctype_from_files(doctype_json_path: str, permissions_json_path: str | None = None) -> None:
	if not os.path.exists(doctype_json_path):
		# Doctype files are installed via normal migrate; patch is best-effort for legacy layouts.
		return
	doctype_doc = _load_json(doctype_json_path)
	doctype_name = doctype_doc.get("name")
	if not doctype_name:
		return
	if frappe.db.exists("DocType", doctype_name):
		return

	if permissions_json_path and os.path.exists(permissions_json_path):
		perms = _load_json(permissions_json_path)
		doctype_doc["permissions"] = [p for p in perms if frappe.db.exists("Role", p.get("role"))]

	frappe.get_doc(doctype_doc).insert(ignore_permissions=True)
	frappe.clear_cache(doctype=doctype_name)


def execute() -> None:
	base = frappe.get_app_path("ferum_custom", "doctype")

	_install_doctype_from_files(
		os.path.join(base, "contract_service_object", "contract_service_object.json"),
		os.path.join(base, "contract_service_object", "permissions", "contract_service_object.json"),
	)
	_install_doctype_from_files(
		os.path.join(base, "act_schedule", "act_schedule.json"),
		os.path.join(base, "act_schedule", "permissions", "act_schedule.json"),
	)
	_install_doctype_from_files(
		os.path.join(base, "service_act_object_item", "service_act_object_item.json"),
		None,
	)
	_install_doctype_from_files(
		os.path.join(base, "service_act", "service_act.json"),
		os.path.join(base, "service_act", "permissions", "service_act.json"),
	)
