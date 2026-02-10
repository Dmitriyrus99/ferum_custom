from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase

from ferum_custom.api.admin import add_user_to_all_projects


def _ensure_user(email: str) -> str:
	email = (email or "").strip().lower()
	if not email:
		raise ValueError("email is empty")
	if frappe.db.exists("User", email):
		return email
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Test",
			"enabled": 1,
			"send_welcome_email": 0,
			"user_type": "System User",
		}
	).insert(ignore_permissions=True)
	return email


def _new_project() -> str:
	project = frappe.new_doc("Project")
	project.project_name = f"Test Project {uuid4().hex[:8]}"
	project.status = "Open"
	if hasattr(project, "ferum_p0_enabled"):
		project.ferum_p0_enabled = 0
	if hasattr(project, "ferum_stage"):
		project.ferum_stage = ""
	project.insert(ignore_permissions=True, ignore_mandatory=True)
	return str(project.name)


class TestAdminAPI(FrappeTestCase):
	def test_add_user_to_all_projects_is_idempotent(self) -> None:
		if not frappe.db.exists("DocType", "Project User"):
			self.skipTest("Project User DocType is not installed")

		frappe.set_user("Administrator")

		user = _ensure_user(f"admin_tool_{uuid4().hex[:8]}@example.com")
		project1 = _new_project()
		project2 = _new_project()

		# Ensure a deterministic starting point: user is a member of project1 only.
		frappe.get_doc(
			{
				"doctype": "Project User",
				"parenttype": "Project",
				"parent": project1,
				"parentfield": "users",
				"user": user,
			}
		).insert(ignore_permissions=True)

		self.assertTrue(
			bool(
				frappe.db.exists(
					"Project User",
					{
						"parenttype": "Project",
						"parentfield": "users",
						"parent": project1,
						"user": user,
					},
				)
			)
		)
		self.assertFalse(
			bool(
				frappe.db.exists(
					"Project User",
					{
						"parenttype": "Project",
						"parentfield": "users",
						"parent": project2,
						"user": user,
					},
				)
			)
		)

		# Dry-run must not insert anything.
		add_user_to_all_projects(user=user, dry_run=1)
		self.assertFalse(
			bool(
				frappe.db.exists(
					"Project User",
					{
						"parenttype": "Project",
						"parentfield": "users",
						"parent": project2,
						"user": user,
					},
				)
			)
		)

		# Real run must insert missing rows, and be safe to repeat.
		add_user_to_all_projects(user=user, dry_run=0)
		self.assertTrue(
			bool(
				frappe.db.exists(
					"Project User",
					{
						"parenttype": "Project",
						"parentfield": "users",
						"parent": project2,
						"user": user,
					},
				)
			)
		)

		add_user_to_all_projects(user=user, dry_run=0)
		self.assertTrue(
			bool(
				frappe.db.exists(
					"Project User",
					{
						"parenttype": "Project",
						"parentfield": "users",
						"parent": project2,
						"user": user,
					},
				)
			)
		)
