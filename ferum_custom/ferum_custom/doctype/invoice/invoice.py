from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

# Conditional import for gspread, as it's an external dependency
try:
	import gspread

	GOOGLE_SHEETS_INTEGRATION_ENABLED = True
except ImportError:
	GOOGLE_SHEETS_INTEGRATION_ENABLED = False


class Invoice(Document):
	def validate(self):
		self.set_customer_and_project()
		self.validate_status_transitions()

	def on_submit(self):
		self.sync_to_google_sheets()

	def set_customer_and_project(self):
		if getattr(self, "contract", None):
			contract = frappe.get_doc("Contract", self.contract)
			if contract.party_type and contract.party_type != "Customer":
				frappe.throw(_("Contract party_type must be Customer."))

			if hasattr(self, "counterparty_type") and self.counterparty_type == "Customer":
				self.counterparty_name = contract.party_name

			if self.meta.has_field("erpnext_project") and frappe.db.has_column("Project", "contract"):
				self.erpnext_project = frappe.db.get_value("Project", {"contract": contract.name}, "name")

	def validate_status_transitions(self):
		old_status = frappe.db.get_value("Invoice", self.name, "status") if not self.is_new() else None

		if old_status == "Draft" and self.status == "Sent" and not self.due_date:
			frappe.throw(_("Due Date is required when sending an Invoice."))
		elif old_status == "Sent" and self.status == "Paid" and self.amount <= 0:
			frappe.throw(_("Cannot mark Invoice as Paid with zero or negative amount."))
		elif old_status == "Draft" and self.status == "Sent":
			pass
		elif old_status == "Sent" and self.status == "Paid":
			pass
		elif old_status == "Sent" and self.status == "Overdue":
			pass
		elif old_status == "Overdue" and self.status == "Paid":
			pass
		elif old_status == "Draft" and self.status == "Cancelled":
			pass
		elif old_status == "Sent" and self.status == "Cancelled":
			pass
		elif old_status and old_status != self.status:
			frappe.throw(_(f"Invalid status transition from {old_status} to {self.status}."))

	def sync_to_google_sheets(self):
		if not GOOGLE_SHEETS_INTEGRATION_ENABLED:
			return

		try:
			gc = gspread.service_account()
			spreadsheet = gc.open("Ferum Invoices Tracker")
			worksheet = spreadsheet.worksheet("Sheet1")

			row_data = [
				self.name,
				getattr(self, "contract", None) or "",
				getattr(self, "erpnext_project", None) or getattr(self, "project", None) or "",
				self.amount,
				self.counterparty_name,
				self.counterparty_type,
				self.status,
				str(self.due_date) if self.due_date else "",
				str(self.creation),
				frappe.session.user,
			]

			cell = worksheet.find(self.name)
			if cell:
				worksheet.update(f"A{cell.row}:J{cell.row}", [row_data])
			else:
				worksheet.append_row(row_data)

		except Exception as e:
			frappe.log_error(
				f"Google Sheets sync failed for Invoice {self.name}: {e}", "Google Sheets Integration"
			)
			frappe.throw(_(f"Failed to sync with Google Sheets: {e}"))
