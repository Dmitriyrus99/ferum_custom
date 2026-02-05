from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


class TestServiceRequest(FrappeTestCase):
	def _company(self) -> str:
		company = frappe.db.get_value("Company", {}, "name")
		self.assertTrue(company)
		return str(company)

	def _customer(self) -> str:
		customer = frappe.db.get_value("Customer", {}, "name")
		self.assertTrue(customer)
		return str(customer)

	def _make_project(self, suffix: str) -> frappe.model.document.Document:
		project = frappe.new_doc("Project")
		project.project_name = f"Test Project {suffix} {frappe.generate_hash(length=6)}"
		if hasattr(project, "company"):
			project.company = self._company()
		if hasattr(project, "customer"):
			project.customer = self._customer()
		# Keep P0 gates disabled for unit tests unless explicitly needed.
		if hasattr(project, "ferum_p0_enabled"):
			project.ferum_p0_enabled = 0
		project.insert(ignore_permissions=True)
		return project

	def _make_project_site(self, project_name: str, suffix: str) -> frappe.model.document.Document:
		ps = frappe.get_doc(
			{
				"doctype": "Project Site",
				"parenttype": "Project",
				"parent": project_name,
				"parentfield": "project_sites",
				"site_name": f"Test Site {suffix} {frappe.generate_hash(length=6)}",
				"address": "Test Address",
				"idx": 1,
			}
		)
		ps.insert(ignore_permissions=True)
		return ps

	def test_sync_customer_and_company_from_project(self) -> None:
		project = self._make_project("A")
		ps = self._make_project_site(project.name, "A")

		sr = frappe.get_doc(
			{
				"doctype": "Service Request",
				"title": "Test SR",
				"erp_project": project.name,
				"project_site": ps.name,
			}
		)
		sr.insert(ignore_permissions=True)

		self.assertEqual(sr.company, project.company)
		self.assertEqual(sr.customer, project.customer)

	def test_project_site_must_belong_to_project(self) -> None:
		project_a = self._make_project("A")
		project_b = self._make_project("B")
		ps_b = self._make_project_site(project_b.name, "B")

		sr = frappe.get_doc(
			{
				"doctype": "Service Request",
				"title": "Test SR mismatch",
				"erp_project": project_a.name,
				"project_site": ps_b.name,
			}
		)
		with self.assertRaises(frappe.exceptions.ValidationError):
			sr.insert(ignore_permissions=True)
