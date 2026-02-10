from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase


def _ensure_user(email: str) -> str:
	email = (email or "").strip().lower()
	if not email:
		raise ValueError("email is empty")

	if frappe.db.exists("User", email):
		return email

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Test",
			"enabled": 1,
			"send_welcome_email": 0,
			"user_type": "System User",
		}
	)
	user.insert(ignore_permissions=True)
	return email


class TestProjectSiteTruthModel(FrappeTestCase):
	def _new_project(self, *, insert: bool = True) -> frappe.model.document.Document:
		project = frappe.new_doc("Project")
		project.project_name = f"Test Project {uuid4().hex[:8]}"
		project.status = "Open"
		if hasattr(project, "ferum_p0_enabled"):
			project.ferum_p0_enabled = 0
		if hasattr(project, "ferum_stage"):
			project.ferum_stage = ""
		if insert:
			project.insert(ignore_permissions=True, ignore_mandatory=True)
		return project

	def test_doctypes_are_correct_shape(self) -> None:
		self.assertTrue(frappe.db.exists("DocType", "Project Site"))
		self.assertEqual(int(frappe.db.get_value("DocType", "Project Site", "istable") or 0), 0)

		# Legacy child table must remain available for backward compatibility.
		self.assertTrue(frappe.db.exists("DocType", "Project Site Row"))
		self.assertEqual(int(frappe.db.get_value("DocType", "Project Site Row", "istable") or 0), 1)

	def test_migration_patch_creates_truth_records_for_legacy_rows(self) -> None:
		if not frappe.db.exists("DocType", "Project Site Row"):
			self.skipTest("Legacy Project Site Row doctype not installed")

		project = self._new_project(insert=False)
		project.append(
			"project_sites",
			{
				"site_name": "Объект 1",
				"address": "Тестовый адрес",
			},
		)
		project.insert(ignore_permissions=True, ignore_mandatory=True)

		row_name = str((project.get("project_sites") or [])[0].name)
		self.assertTrue(frappe.db.exists("Project Site Row", row_name))

		from ferum_custom.patches.v15_10.migrate_project_site_row_to_truth import execute

		execute()

		self.assertTrue(frappe.db.exists("Project Site", row_name))
		# Idempotent rerun.
		execute()
		self.assertTrue(frappe.db.exists("Project Site", row_name))

	def test_project_site_permission_scopes_by_project_access(self) -> None:
		from ferum_custom.security.project_site_permissions import (
			project_site_has_permission,
			project_site_permission_query_conditions,
		)

		engineer = _ensure_user("ps_engineer@example.com")
		outsider = _ensure_user("ps_outsider@example.com")

		project = self._new_project(insert=True)

		site = frappe.get_doc(
			{
				"doctype": "Project Site",
				"project": project.name,
				"site_name": "Объект",
				"address": "Адрес",
				"default_engineer": engineer,
			}
		)
		site.insert(ignore_permissions=True, ignore_mandatory=True)

		cond = project_site_permission_query_conditions(engineer)
		self.assertIn(project.name, cond)
		self.assertTrue(bool(cond))
		self.assertTrue(bool(project_site_has_permission(site, user=engineer)))

		cond2 = project_site_permission_query_conditions(outsider)
		self.assertEqual(cond2, "1=0")
		self.assertFalse(bool(project_site_has_permission(site, user=outsider)))
