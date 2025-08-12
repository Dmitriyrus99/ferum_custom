import frappe
from frappe.model.document import Document
from frappe import _

class Invoice(Document):
    def validate(self):
        self.validate_status_transitions()

    def on_submit(self):
        self.sync_to_google_sheets()

    def validate_status_transitions(self):
        old_status = frappe.db.get_value("Invoice", self.name, "status") if not self.is_new() else None

        if old_status == "Draft" and self.status == "Sent" and not self.due_date:
            frappe.throw(_("Due Date is required when sending an Invoice."))
        elif old_status == "Sent" and self.status == "Paid" and self.amount <= 0:
            frappe.throw(_("Cannot mark Invoice as Paid with zero or negative amount."))
        # Add more transitions as per the workflow diagram in Technical_Specification_full.md
        # Draft --> Sent : Отправить клиенту / Утвердить к оплате
        # Sent --> Paid : Отметить как оплаченный
        # Sent --> Overdue : Просрочен
        # Overdue --> Paid : Отметить как оплаченный
        # Draft --> Cancelled : Отменить
        # Sent --> Cancelled : Отменить

    def sync_to_google_sheets(self):
        # Placeholder for Google Sheets integration logic
        # This function would typically:
        # 1. Authenticate with Google Sheets API.
        # 2. Open the target spreadsheet and worksheet.
        # 3. Append or update a row with Invoice data.
        frappe.msgprint(_("Invoice Google Sheets sync placeholder executed. Configure actual integration."))
        # Example (requires gspread and proper authentication setup):
        # import gspread
        # gc = gspread.service_account()
        # spreadsheet = gc.open("Your Invoice Spreadsheet Name")
        # worksheet = spreadsheet.worksheet("Sheet1")
        # worksheet.append_row([self.name, self.project, self.amount, self.status, self.due_date])
