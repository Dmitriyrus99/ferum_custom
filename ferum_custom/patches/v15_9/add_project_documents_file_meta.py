from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
	if not frappe.db.exists("DocType", "File"):
		return

	doc_type_options = "\n".join(
		[
			"Договоры с заказчиком",
			"Договоры с подрядчиками/исполнителями",
			"Удостоверения и разрешительные документы исполнителей",
			"Закрывающие документы с подписью заказчика",
			"Входящие письма от заказчика",
			"Исходящие письма в адрес заказчика",
		]
	)

	create_custom_fields(
		{
			"File": [
				{
					"fieldname": "ferum_doc_meta_section",
					"label": "Документы (Ferum)",
					"fieldtype": "Section Break",
					"insert_after": "uploaded_to_google_drive",
					"collapsible": 1,
					"collapsed": 1,
				},
				{
					"fieldname": "ferum_doc_title",
					"label": "Наименование документа",
					"fieldtype": "Data",
					"insert_after": "ferum_doc_meta_section",
				},
				{
					"fieldname": "ferum_doc_type",
					"label": "Тип документа",
					"fieldtype": "Select",
					"options": doc_type_options,
					"insert_after": "ferum_doc_title",
				},
				{
					"fieldname": "ferum_contract",
					"label": "Контракт",
					"fieldtype": "Link",
					"options": "Contract",
					"insert_after": "ferum_doc_type",
				},
				{
					"fieldname": "ferum_drive_file_id",
					"label": "Google Drive File ID",
					"fieldtype": "Data",
					"insert_after": "ferum_contract",
					"read_only": 1,
					"hidden": 1,
				},
			]
		},
		ignore_validate=True,
	)

	frappe.clear_cache()

