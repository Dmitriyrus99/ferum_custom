from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from ferum_custom.api.telegram_bot import list_projects


class TestTelegramProjectAccess(FrappeTestCase):
	def _ensure_customer(self) -> str | None:
		if not frappe.db.exists("DocType", "Customer"):
			return None
		customer = frappe.db.get_value("Customer", {}, "name")
		if customer:
			return str(customer)

		customer_doc = frappe.new_doc("Customer")
		customer_doc.customer_name = f"Test Customer {frappe.generate_hash(length=6)}"
		if hasattr(customer_doc, "customer_type"):
			customer_doc.customer_type = "Individual"
		customer_doc.insert(ignore_permissions=True)
		return str(customer_doc.name)

	def test_project_users_grant_access_to_list_projects(self) -> None:
		if not frappe.db.exists("DocType", "Telegram User Link"):
			self.skipTest("Telegram User Link DocType is not installed")
		if not frappe.db.exists("DocType", "Project User"):
			self.skipTest("Project User DocType is not installed")

		user_email = f"tg_user_{frappe.generate_hash(length=6)}@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": user_email,
				"first_name": "TG",
				"last_name": "User",
				"enabled": 1,
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)

		chat_id = 900_000_001
		frappe.get_doc(
			{
				"doctype": "Telegram User Link",
				"user": user.name,
				"chat_id": str(chat_id),
			}
		).insert(ignore_permissions=True)

		project = frappe.new_doc("Project")
		project.project_name = f"Test Project {frappe.generate_hash(length=6)}"
		if hasattr(project, "company"):
			project.company = frappe.db.get_value("Company", {}, "name")
		if hasattr(project, "customer"):
			project.customer = self._ensure_customer()
		if hasattr(project, "ferum_p0_enabled"):
			project.ferum_p0_enabled = 0
		project.insert(ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Project User",
				"parenttype": "Project",
				"parent": project.name,
				"parentfield": "users",
				"user": user.name,
			}
		).insert(ignore_permissions=True)

		rows = list_projects(chat_id)
		names = {str(r.get("name") or "").strip() for r in (rows or [])}
		self.assertIn(project.name, names)
