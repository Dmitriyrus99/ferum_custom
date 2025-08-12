import frappe
import unittest
from unittest.mock import patch, MagicMock

class TestMaintenanceSchedule(unittest.TestCase):
    def setUp(self):
        # Create dummy DocTypes for testing
        if not frappe.db.exists("DocType", "MaintenanceSchedule"):
            frappe.get_doc({"doctype": "DocType", "name": "MaintenanceSchedule", "module": "Ferum Custom", "autoname": "MSCH-.####", "fields": [
                {"fieldname": "schedule_name", "fieldtype": "Data", "label": "Schedule Name"},
                {"fieldname": "customer", "fieldtype": "Link", "label": "Customer", "options": "Customer"},
                {"fieldname": "service_project", "fieldtype": "Link", "label": "Service Project", "options": "ServiceProject"},
                {"fieldname": "frequency", "fieldtype": "Select", "label": "Frequency", "options": "Daily\nWeekly\nMonthly\nAnnually"},
                {"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date"},
                {"fieldname": "end_date", "fieldtype": "Date", "label": "End Date"},
                {"fieldname": "next_due_date", "fieldtype": "Date", "label": "Next Due Date"},
                {"fieldname": "items", "fieldtype": "Table", "label": "Items", "options": "MaintenanceScheduleItem"}
            ]}).insert()
        if not frappe.db.exists("DocType", "MaintenanceScheduleItem"):
            frappe.get_doc({"doctype": "DocType", "name": "MaintenanceScheduleItem", "module": "Ferum Custom", "istable": 1, "fields": [
                {"fieldname": "service_object", "fieldtype": "Link", "label": "Service Object", "options": "ServiceObject"}
            ]}).insert()
        if not frappe.db.exists("DocType", "ServiceRequest"):
            frappe.get_doc({"doctype": "DocType", "name": "ServiceRequest", "module": "Ferum Custom", "fields": [
                {"fieldname": "customer", "fieldtype": "Link", "label": "Customer", "options": "Customer"},
                {"fieldname": "service_project", "fieldtype": "Link", "label": "Service Project", "options": "ServiceProject"},
                {"fieldname": "service_object", "fieldtype": "Link", "label": "Service Object", "options": "ServiceObject"},
                {"fieldname": "subject", "fieldtype": "Data", "label": "Subject"},
                {"fieldname": "description", "fieldtype": "Text", "label": "Description"},
                {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Open\nIn Progress\nCompleted\nClosed"}
            ]}).insert()
        if not frappe.db.exists("DocType", "Customer"):
            frappe.get_doc({"doctype": "DocType", "name": "Customer", "module": "Ferum Custom"}).insert()
        if not frappe.db.exists("DocType", "ServiceProject"):
            frappe.get_doc({"doctype": "DocType", "name": "ServiceProject", "module": "Ferum Custom"}).insert()
        if not frappe.db.exists("DocType", "ServiceObject"):
            frappe.get_doc({"doctype": "DocType", "name": "ServiceObject", "module": "Ferum Custom"}).insert()

    @patch('frappe.utils.nowdate', return_value='2025-08-12')
    @patch('frappe.new_doc')
    @patch('frappe.get_list')
    @patch('frappe.db.commit')
    def test_generate_service_requests_from_schedule(self, mock_commit, mock_get_list, mock_new_doc, mock_nowdate):
        from ferum_custom.doctype.MaintenanceSchedule.maintenance_schedule import generate_service_requests_from_schedule

        # Mock a schedule that is due today
        mock_schedule = MagicMock()
        mock_schedule.name = "MSCH-0001"
        mock_schedule.customer = "Test Customer"
        mock_schedule.service_project = "Test Project"
        mock_schedule.next_due_date = "2025-08-12"
        mock_schedule.end_date = None
        mock_schedule.get.return_value = [
            {"service_object": "SO-001", "description": "Item 1"},
            {"service_object": "SO-002", "description": "Item 2"}
        ]
        mock_get_list.return_value = [mock_schedule]

        # Mock new_doc to return a mock ServiceRequest
        mock_sr = MagicMock()
        mock_new_doc.return_value = mock_sr

        generate_service_requests_from_schedule()

        # Assertions
        mock_get_list.assert_called_once_with("MaintenanceSchedule", filters={'next_due_date': ['<=', '2025-08-12'], 'docstatus': 0}, fields=['*'])
        self.assertEqual(mock_new_doc.call_count, 2) # Two service requests should be created
        mock_sr.save.call_count == 2
        mock_commit.call_count == 2
        mock_schedule.save.assert_called_once() # Schedule should be updated

class TestServiceRequestSLA(unittest.TestCase):
    def setUp(self):
        if not frappe.db.exists("DocType", "ServiceRequest"):
            frappe.get_doc({"doctype": "DocType", "name": "ServiceRequest", "module": "Ferum Custom", "fields": [
                {"fieldname": "title", "fieldtype": "Data", "label": "Title"},
                {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Open\nIn Progress\nCompleted\nClosed"},
                {"fieldname": "priority", "fieldtype": "Select", "label": "Priority", "options": "Low\nMedium\nHigh"},
                {"fieldname": "sla_deadline", "fieldtype": "Datetime", "label": "SLA Deadline"},
                {"fieldname": "type", "fieldtype": "Select", "label": "Type", "options": "Emergency\nRoutine"}
            ]}).insert()

    @patch('frappe.utils.nowdate', return_value='2025-08-13') # One day after deadline
    @patch('frappe.sendmail')
    @patch('requests.post')
    @patch('frappe.log_error')
    @patch('frappe.msgprint')
    def test_check_sla_breach_notification(self, mock_msgprint, mock_log_error, mock_requests_post, mock_sendmail, mock_nowdate):
        from ferum_custom.doctype.ServiceRequest.service_request import ServiceRequest

        # Mock a ServiceRequest that has breached SLA
        sr = ServiceRequest({
            "name": "SR-001",
            "title": "SLA Test",
            "status": "Open",
            "priority": "High",
            "sla_deadline": "2025-08-12 10:00:00",
            "type": "Emergency",
            "creation": "2025-08-12 06:00:00" # Creation time before deadline
        })
        sr.is_new = MagicMock(return_value=False)
        sr.get = MagicMock(side_effect=sr.get)

        # Mock frappe.db.get_value for old_status check
        with patch('frappe.db.get_value', return_value="Open"):
            sr.check_sla_breach()

        # Assertions
        mock_msgprint.assert_called_once() # Should show msgprint
        mock_log_error.assert_called_once() # Should log error
        mock_requests_post.assert_called_once() # Should attempt Telegram notification
        mock_sendmail.assert_called_once() # Should attempt Email notification

class TestCustomAttachment(unittest.TestCase):
    def setUp(self):
        if not frappe.db.exists("DocType", "CustomAttachment"):
            frappe.get_doc({"doctype": "DocType", "name": "CustomAttachment", "module": "Ferum Custom", "fields": [
                {"fieldname": "file_url", "fieldtype": "Attach", "label": "File URL"},
                {"fieldname": "google_drive_file_id", "fieldtype": "Data", "label": "Google Drive File ID"},
                {"fieldname": "file_name", "fieldtype": "Data", "label": "File Name"}
            ]}).insert()

    @patch('frappe.get_site_path', side_effect=lambda *args: os.path.join("mock_site_path", *args))
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('frappe.conf', new_callable=MagicMock)
    @patch('google.oauth2.service_account.Credentials.from_service_account_file', new_callable=MagicMock)
    @patch('googleapiclient.discovery.build', new_callable=MagicMock)
    @patch('frappe.msgprint')
    @patch('frappe.log_error')
    def test_upload_to_google_drive(self, mock_log_error, mock_msgprint, mock_build, mock_credentials, mock_open, mock_exists, mock_get_site_path):
        from ferum_custom.doctype.CustomAttachment.custom_attachment import CustomAttachment

        mock_build.return_value.files.return_value.create.return_value.execute.return_value = {'id': 'mock_drive_id', 'webViewLink': 'mock_webview_link'}
        mock_credentials.from_service_account_file.return_value = MagicMock()
        mock_open.return_value = MagicMock()
        mock_exists.return_value = True
        mock_get_site_path.return_value = "mock_file_path"
        mock_msgprint.return_value = None
        mock_log_error.return_value = None
        frappe.conf.google_drive_folder_id = "mock_folder_id"

        attachment = CustomAttachment({
            "file_url": "/files/test.pdf",
            "file_name": "test.pdf"
        })
        attachment.upload_to_google_drive()

        self.assertEqual(attachment.google_drive_file_id, 'mock_drive_id')
        self.assertEqual(attachment.file_url, 'mock_webview_link')
        mock_msgprint.assert_called_once()

    @patch('frappe.conf', new_callable=MagicMock)
    @patch('google.oauth2.service_account.Credentials.from_service_account_file', new_callable=MagicMock)
    @patch('googleapiclient.discovery.build', new_callable=MagicMock)
    @patch('frappe.msgprint')
    @patch('frappe.log_error')
    def test_delete_from_google_drive(self, mock_log_error, mock_msgprint, mock_build, mock_credentials, mock_conf):
        from ferum_custom.doctype.CustomAttachment.custom_attachment import CustomAttachment

        mock_build.return_value.files.return_value.delete.return_value.execute.return_value = None
        mock_credentials.from_service_account_file.return_value = MagicMock()
        mock_msgprint.return_value = None
        mock_log_error.return_value = None
        mock_conf.google_drive_folder_id = "mock_folder_id"

        attachment = CustomAttachment({
            "google_drive_file_id": "mock_drive_id",
            "file_name": "test.pdf"
        })
        attachment.delete_from_google_drive()

        mock_msgprint.assert_called_once()

class TestInvoiceStatusTransitions(unittest.TestCase):
    def setUp(self):
        if not frappe.db.exists("DocType", "Invoice"):
            frappe.get_doc({"doctype": "DocType", "name": "Invoice", "module": "Ferum Custom", "fields": [
                {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Draft\nSent\nPaid\nOverdue\nCancelled"},
                {"fieldname": "due_date", "fieldtype": "Date", "label": "Due Date"},
                {"fieldname": "amount", "fieldtype": "Currency", "label": "Amount"}
            ]}).insert()

    @patch('frappe.db.get_value')
    @patch('frappe.throw')
    def test_valid_transitions(self, mock_frappe_throw, mock_get_value):
        from ferum_custom.doctype.Invoice.invoice import Invoice

        # Test Draft -> Sent (with due_date)
        mock_get_value.return_value = "Draft"
        invoice = Invoice({"name": "INV-001", "status": "Sent", "due_date": "2025-08-15"})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_not_called()

        # Test Sent -> Paid
        mock_get_value.return_value = "Sent"
        invoice = Invoice({"name": "INV-001", "status": "Paid", "amount": 100})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_not_called()

        # Test Sent -> Overdue
        mock_get_value.return_value = "Sent"
        invoice = Invoice({"name": "INV-001", "status": "Overdue"})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_not_called()

        # Test Overdue -> Paid
        mock_get_value.return_value = "Overdue"
        invoice = Invoice({"name": "INV-001", "status": "Paid", "amount": 100})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_not_called()

        # Test Draft -> Cancelled
        mock_get_value.return_value = "Draft"
        invoice = Invoice({"name": "INV-001", "status": "Cancelled"})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_not_called()

        # Test Sent -> Cancelled
        mock_get_value.return_value = "Sent"
        invoice = Invoice({"name": "INV-001", "status": "Cancelled"})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_not_called()

    @patch('frappe.db.get_value')
    @patch('frappe.throw')
    def test_invalid_transitions(self, mock_frappe_throw, mock_get_value):
        from ferum_custom.doctype.Invoice.invoice import Invoice

        # Test Draft -> Sent (without due_date)
        mock_get_value.return_value = "Draft"
        invoice = Invoice({"name": "INV-001", "status": "Sent", "due_date": None})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_called_with(unittest.mock.ANY) # Should throw error
        mock_frappe_throw.reset_mock()

        # Test Sent -> Paid (zero amount)
        mock_get_value.return_value = "Sent"
        invoice = Invoice({"name": "INV-001", "status": "Paid", "amount": 0})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_called_with(unittest.mock.ANY) # Should throw error
        mock_frappe_throw.reset_mock()

        # Test invalid arbitrary transition (e.g., Paid -> Sent)
        mock_get_value.return_value = "Paid"
        invoice = Invoice({"name": "INV-001", "status": "Sent"})
        invoice.is_new = MagicMock(return_value=False)
        invoice.validate_status_transitions()
        mock_frappe_throw.assert_called_with(unittest.mock.ANY) # Should throw error
        mock_frappe_throw.reset_mock()

class TestPayrollEntryCustom(unittest.TestCase):
    def setUp(self):
        if not frappe.db.exists("DocType", "PayrollEntryCustom"):
            frappe.get_doc({"doctype": "DocType", "name": "PayrollEntryCustom", "module": "Ferum Custom", "fields": [
                {"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date"},
                {"fieldname": "end_date", "fieldtype": "Date", "label": "End Date"},
                {"fieldname": "base_salary", "fieldtype": "Currency", "label": "Base Salary"},
                {"fieldname": "additional_pay", "fieldtype": "Currency", "label": "Additional Pay"},
                {"fieldname": "total_deduction", "fieldtype": "Currency", "label": "Total Deduction"},
                {"fieldname": "total_payable", "fieldtype": "Currency", "label": "Total Payable"},
                {"fieldname": "employee", "fieldtype": "Link", "label": "Employee", "options": "Employee"}
            ]}).insert()
        if not frappe.db.exists("DocType", "ServiceReport"):
            frappe.get_doc({"doctype": "DocType", "name": "ServiceReport", "module": "Ferum Custom", "fields": [
                {"fieldname": "posting_date", "fieldtype": "Date", "label": "Posting Date"},
                {"fieldname": "custom_assigned_engineer", "fieldtype": "Link", "label": "Assigned Engineer", "options": "User"},
                {"fieldname": "custom_bonus_amount", "fieldtype": "Currency", "label": "Bonus Amount"}
            ]}).insert()
        if not frappe.db.exists("DocType", "Employee"):
            frappe.get_doc({"doctype": "DocType", "name": "Employee", "module": "Ferum Custom"}).insert()

    @patch('frappe.get_list')
    def test_calculate_total_payable_with_bonus(self, mock_get_list):
        from ferum_custom.doctype.PayrollEntryCustom.payroll_entry_custom import PayrollEntryCustom

        # Mock ServiceReports with bonus amounts
        mock_get_list.return_value = [
            {"name": "SR-001", "custom_bonus_amount": 50.0},
            {"name": "SR-002", "custom_bonus_amount": 75.0}
        ]

        payroll_entry = PayrollEntryCustom({
            "start_date": "2025-08-01",
            "end_date": "2025-08-31",
            "base_salary": 1000.0,
            "additional_pay": 50.0,
            "total_deduction": 200.0,
            "employee": "test_engineer"
        })
        payroll_entry.is_new = MagicMock(return_value=True)
        payroll_entry.before_save()

        # Expected total_payable = base_salary + additional_pay + (50 + 75) - total_deduction
        # = 1000 + 50 + 125 - 200 = 975
        self.assertEqual(payroll_entry.total_payable, 975.0)

        mock_get_list.assert_called_once_with(
            "ServiceReport",
            filters={
                "custom_assigned_engineer": "test_engineer",
                "posting_date": [">=", "2025-08-01"],
                "posting_date": ["<=", "2025-08-31"]
            },
            fields=["name", "custom_bonus_amount"]
        )

    @patch('frappe.get_list', return_value=[]) # No bonuses
    def test_calculate_total_payable_no_bonus(self, mock_get_list):
        from ferum_custom.doctype.PayrollEntryCustom.payroll_entry_custom import PayrollEntryCustom

        payroll_entry = PayrollEntryCustom({
            "start_date": "2025-08-01",
            "end_date": "2025-08-31",
            "base_salary": 1000.0,
            "additional_pay": 50.0,
            "total_deduction": 200.0,
            "employee": "test_engineer"
        })
        payroll_entry.is_new = MagicMock(return_value=True)
        payroll_entry.before_save()

        # Expected total_payable = 1000 + 50 - 200 = 850
        self.assertEqual(payroll_entry.total_payable, 850.0)

class TestInvoiceGoogleSheets(unittest.TestCase):
    def setUp(self):
        if not frappe.db.exists("DocType", "Invoice"):
            frappe.get_doc({"doctype": "DocType", "name": "Invoice", "module": "Ferum Custom", "fields": [
                {"fieldname": "name", "fieldtype": "Data", "label": "Name"},
                {"fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "ServiceProject"},
                {"fieldname": "amount", "fieldtype": "Currency", "label": "Amount"},
                {"fieldname": "counterparty_name", "fieldtype": "Data", "label": "Counterparty Name"},
                {"fieldname": "counterparty_type", "fieldtype": "Select", "label": "Counterparty Type", "options": "Customer\nSubcontractor"},
                {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Draft\nSent\nPaid\nOverdue\nCancelled"},
                {"fieldname": "due_date", "fieldtype": "Date", "label": "Due Date"},
                {"fieldname": "creation", "fieldtype": "Datetime", "label": "Creation"}
            ]}).insert()

    @patch('gspread.service_account')
    @patch('frappe.msgprint')
    @patch('frappe.log_error')
    @patch('frappe.conf', new_callable=MagicMock)
    def test_sync_to_google_sheets(self, mock_conf, mock_log_error, mock_msgprint, mock_gspread_service_account):
        from ferum_custom.doctype.Invoice.invoice import Invoice, GOOGLE_SHEETS_INTEGRATION_ENABLED

        if not GOOGLE_SHEETS_INTEGRATION_ENABLED:
            self.skipTest("gspread not installed, skipping Google Sheets integration test.")

        # Mock gspread objects
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_gspread_service_account.return_value = mock_gc
        mock_gc.open.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.return_value = mock_worksheet

        # Mock find to simulate no existing invoice
        mock_worksheet.find.return_value = None

        invoice = Invoice({
            "name": "INV-001",
            "project": "PROJ-001",
            "amount": 100.0,
            "counterparty_name": "Test Customer",
            "counterparty_type": "Customer",
            "status": "Sent",
            "due_date": "2025-09-01",
            "creation": "2025-08-12 10:00:00"
        })
        invoice.sync_to_google_sheets()

        mock_gspread_service_account.assert_called_once()
        mock_gc.open.assert_called_once_with("Ferum Invoices Tracker")
        mock_spreadsheet.worksheet.assert_called_once_with("Sheet1")
        mock_worksheet.find.assert_called_once_with("INV-001")
        mock_worksheet.append_row.assert_called_once() # Should append new row
        mock_msgprint.assert_called_once()
        mock_log_error.assert_not_called()

        # Test update existing invoice
        mock_worksheet.find.return_value = MagicMock(row=5) # Simulate invoice found at row 5
        invoice.sync_to_google_sheets()
        mock_worksheet.update.assert_called_once() # Should update existing row

    @patch('gspread.service_account', side_effect=Exception("Auth Error"))
    @patch('frappe.msgprint')
    @patch('frappe.log_error')
    @patch('frappe.throw')
    def test_sync_to_google_sheets_error_handling(self, mock_frappe_throw, mock_log_error, mock_msgprint, mock_gspread_service_account):
        from ferum_custom.doctype.Invoice.invoice import Invoice, GOOGLE_SHEETS_INTEGRATION_ENABLED

        if not GOOGLE_SHEETS_INTEGRATION_ENABLED:
            self.skipTest("gspread not installed, skipping Google Sheets integration test.")

        invoice = Invoice({"name": "INV-002"})
        invoice.sync_to_google_sheets()

        mock_log_error.assert_called_once()
        mock_frappe_throw.assert_called_once()


if __name__ == '__main__':
    unittest.main()
