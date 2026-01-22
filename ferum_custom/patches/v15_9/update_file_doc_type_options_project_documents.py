from __future__ import annotations

import frappe


def execute() -> None:
	"""Ensure File.ferum_doc_type has the full fixed list of project document types."""

	if not frappe.db.exists("DocType", "Custom Field"):
		return

	name = frappe.db.get_value("Custom Field", {"dt": "File", "fieldname": "ferum_doc_type"}, "name")
	if not name:
		return

	doc_types = [
		"Договоры с заказчиком",
		"Договоры с подрядчиками/исполнителями",
		"Удостоверения и разрешительные документы исполнителей",
		"Закрывающие документы с подписью заказчика",
		"Входящие письма от заказчика",
		"Исходящие письма в адрес заказчика",
		"Служебные / внутренние документы проекта",
	]
	desired = "\n".join(doc_types)

	cf = frappe.get_doc("Custom Field", name)
	current = str(getattr(cf, "options", "") or "").strip()
	if current != desired:
		cf.options = desired
		cf.save(ignore_permissions=True)

	frappe.clear_cache()

