from __future__ import annotations

from frappe.tests.utils import FrappeTestCase

from ferum_custom.setup.audit import check_hooks_imports


class TestRuntimeAudit(FrappeTestCase):
	def test_hooks_targets_import(self) -> None:
		issues = check_hooks_imports()
		self.assertEqual(issues, [])
