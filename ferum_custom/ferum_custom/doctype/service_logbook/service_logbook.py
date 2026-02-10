from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class ServiceLogbook(Document):
	def validate(self):
		if not getattr(self, "year", None):
			self.year = now_datetime().year
		if not getattr(self, "book_type", None):
			self.book_type = "Electronic"
		self._validate_unique()

	def _validate_unique(self) -> None:
		project_site = str(getattr(self, "project_site", "") or "").strip()
		try:
			year = int(getattr(self, "year", 0) or 0)
		except Exception:
			year = 0
		book_type = str(getattr(self, "book_type", "") or "").strip()
		if not project_site or not year or not book_type:
			return

		other = frappe.db.get_value(
			self.doctype,
			{
				"project_site": project_site,
				"year": year,
				"book_type": book_type,
				"name": ["!=", self.name],
			},
			"name",
		)
		if other:
			frappe.throw(
				_("Service Logbook already exists for this Project Site/year/type: {0}.").format(
					frappe.bold(other)
				)
			)
