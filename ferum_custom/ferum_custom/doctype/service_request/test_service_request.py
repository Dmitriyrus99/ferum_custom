from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

# Keep test record generation minimal for this app's doctypes.
#
# `bench run-tests --app ferum_custom` runs only this app's tests; however, Frappe's default
# `make_test_records()` recursion can traverse far into ERPNext's dependency graph and hit
# optional doctypes that may not be installed in this bench (e.g. "Payment Gateway").
test_ignore = [
	"Company",
	"Contract",
	"Currency",
	"Customer",
	"Project",
	"Project Site",
	"Project Site Row",
	"SLA Policy",
	"Service Department",
	"Service Object",
	"Service Project",
	"Service Report",
	"User",
]


class TestServiceRequest(FrappeTestCase):
	def _company(self) -> str:
		company = frappe.db.get_value("Company", {}, "name")
		self.assertTrue(company)
		return str(company)

	def _customer(self) -> str:
		customer = frappe.db.get_value("Customer", {}, "name")
		if customer:
			return str(customer)

		customer_doc = frappe.new_doc("Customer")
		customer_doc.customer_name = f"Test Customer {frappe.generate_hash(length=6)}"
		if hasattr(customer_doc, "customer_type"):
			customer_doc.customer_type = "Individual"
		if hasattr(customer_doc, "customer_group"):
			customer_doc.customer_group = (
				frappe.db.get_value("Customer Group", {"is_group": 1}, "name") or "All Customer Groups"
			)
		if hasattr(customer_doc, "territory"):
			customer_doc.territory = (
				frappe.db.get_value("Territory", {"is_group": 1}, "name") or "All Territories"
			)
		customer_doc.insert(ignore_permissions=True)
		return str(customer_doc.name)

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
				"project": project_name,
				"site_name": f"Test Site {suffix} {frappe.generate_hash(length=6)}",
				"address": "Test Address",
			}
		)
		ps.insert(ignore_permissions=True, ignore_mandatory=True)
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

	def test_registered_datetime_is_set_on_insert(self) -> None:
		project = self._make_project("A")
		ps = self._make_project_site(project.name, "A")

		sr = frappe.get_doc(
			{
				"doctype": "Service Request",
				"title": "Test SR registered",
				"erp_project": project.name,
				"project_site": ps.name,
			}
		)
		sr.insert(ignore_permissions=True)

		self.assertTrue(getattr(sr, "registered_datetime", None))

	def test_external_source_requires_reference_when_reported_differs(self) -> None:
		project = self._make_project("A")
		ps = self._make_project_site(project.name, "A")

		sr = frappe.get_doc(
			{
				"doctype": "Service Request",
				"title": "Test SR external evidence",
				"erp_project": project.name,
				"project_site": ps.name,
				"source_channel": "Email",
				"registered_datetime": now_datetime(),
				"reported_datetime": add_to_date(now_datetime(), hours=-2),
			}
		)
		with self.assertRaises(frappe.exceptions.ValidationError):
			sr.insert(ignore_permissions=True)
