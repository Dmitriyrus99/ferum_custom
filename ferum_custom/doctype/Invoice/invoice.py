import frappe
from frappe.model.document import Document
from frappe import _

# Conditional import for gspread, as it's an external dependency
try:
    import gspread
    GOOGLE_SHEETS_INTEGRATION_ENABLED = True
except ImportError:
    GOOGLE_SHEETS_INTEGRATION_ENABLED = False
    frappe.log_error("gspread library not found. Google Sheets integration will be disabled.", "Google Sheets Integration")

class Invoice(Document):
    def validate(self):
        self.set_customer_and_project()
        self.validate_status_transitions()

    def on_submit(self):
        self.sync_to_google_sheets()

    def set_customer_and_project(self):
        # Prefer new model (Contract -> standard Project) and keep legacy project link read-only.
        if getattr(self, "contract", None):
            contract = frappe.get_doc("Contract", self.contract)
            if contract.party_type and contract.party_type != "Customer":
                frappe.throw(_("Contract party_type must be Customer."))

            if hasattr(self, "counterparty_type") and self.counterparty_type == "Customer":
                self.counterparty_name = contract.party_name

            if frappe.db.has_column("Project", "contract"):
                self.erpnext_project = frappe.db.get_value("Project", {"contract": contract.name}, "name")

    def validate_status_transitions(self):
        old_status = frappe.db.get_value("Invoice", self.name, "status") if not self.is_new() else None

        if old_status == "Draft" and self.status == "Sent" and not self.due_date:
            frappe.throw(_("Due Date is required when sending an Invoice."))
        elif old_status == "Sent" and self.status == "Paid" and self.amount <= 0:
            frappe.throw(_("Cannot mark Invoice as Paid with zero or negative amount."))
        elif old_status == "Draft" and self.status == "Sent":
            pass # Allowed
        elif old_status == "Sent" and self.status == "Paid":
            pass # Allowed
        elif old_status == "Sent" and self.status == "Overdue":
            pass # Allowed
        elif old_status == "Overdue" and self.status == "Paid":
            pass # Allowed
        elif old_status == "Draft" and self.status == "Cancelled":
            pass # Allowed
        elif old_status == "Sent" and self.status == "Cancelled":
            pass # Allowed
        elif old_status and old_status != self.status: # Prevent invalid transitions
            frappe.throw(_(f"Invalid status transition from {old_status} to {self.status}."))

    def sync_to_google_sheets(self):
        if not GOOGLE_SHEETS_INTEGRATION_ENABLED:
            frappe.msgprint(_("Google Sheets integration is disabled. gspread library not found."))
            return

        try:
            # Authenticate with Google Sheets API using service account credentials
            # Ensure your service account JSON key file is accessible and configured.
            # For Frappe, you might store the path to the key file in site_config.json or a custom setting DocType.
            # For this example, we assume service_account() can find credentials.
            gc = gspread.service_account() # Assumes GOOGLE_APPLICATION_CREDENTIALS env var is set or key file is in default location

            # Open the target spreadsheet by its name or ID
            # Replace "Your Invoice Spreadsheet Name or ID" with your actual spreadsheet name/ID
            spreadsheet = gc.open("Ferum Invoices Tracker") # Or gc.open_by_key("YOUR_SPREADSHEET_ID")
            worksheet = spreadsheet.worksheet("Sheet1") # Or your specific worksheet name

            # Prepare data to append/update
            # Example row data. Adjust columns as per your Google Sheet structure.
            row_data = [
                self.name, # Invoice ID
                getattr(self, "contract", None) or "", # Linked Contract
                getattr(self, "erpnext_project", None) or self.project or "", # Linked Project (new/legacy)
                self.amount, # Invoice Amount
                self.counterparty_name, # Client/Subcontractor Name
                self.counterparty_type, # Type (Customer/Subcontractor)
                self.status, # Invoice Status
                str(self.due_date) if self.due_date else "", # Due Date
                str(self.creation), # Creation Timestamp
                frappe.session.user # User who created/submitted
            ]

            # Find if invoice already exists to update, otherwise append
            # This is a simplified check. A more robust solution would use a unique identifier.
            cell = worksheet.find(self.name) # Search by Invoice ID
            if cell:
                # Update existing row
                worksheet.update(f'A{cell.row}:J{cell.row}', [row_data]) # Adjust range (A:J) as per your columns
                frappe.msgprint(_(f"Invoice {self.name} updated in Google Sheets."))
            else:
                # Append new row
                worksheet.append_row(row_data)
                frappe.msgprint(_(f"Invoice {self.name} appended to Google Sheets."))

        except Exception as e:
            frappe.log_error(f"Google Sheets sync failed for Invoice {self.name}: {e}", "Google Sheets Integration Error")
            frappe.throw(_(f"Failed to sync with Google Sheets: {e}"))
