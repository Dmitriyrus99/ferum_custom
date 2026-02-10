from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class ServiceLogEntry(Document):
	def validate(self):
		self._sync_from_logbook()
		if not getattr(self, "performed_at", None):
			self.performed_at = now_datetime()

	def _sync_from_logbook(self) -> None:
		logbook = str(getattr(self, "logbook", "") or "").strip()
		if not logbook:
			return
		if not frappe.db.exists("Service Logbook", logbook):
			frappe.throw(_("Service Logbook not found: {0}.").format(frappe.bold(logbook)))
		ps = frappe.db.get_value("Service Logbook", logbook, "project_site")
		ps = str(ps or "").strip() or None
		if self.meta.has_field("project_site"):
			self.project_site = ps
