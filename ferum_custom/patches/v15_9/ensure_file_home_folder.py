from __future__ import annotations

import frappe


def execute():
	"""Ensure core File folders exist (Home + Attachments).

	If the root folder `Home` is missing, any file upload fails with LinkValidationError.
	"""

	if not frappe.db.exists("File", "Home"):
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "Home",
				"is_folder": 1,
				"is_home_folder": 1,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
	else:
		frappe.db.set_value("File", "Home", {"is_folder": 1, "is_home_folder": 1}, update_modified=False)

	if not frappe.db.get_value("File", {"is_attachments_folder": 1}, "name"):
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "Attachments",
				"is_folder": 1,
				"is_attachments_folder": 1,
				"folder": "Home",
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
