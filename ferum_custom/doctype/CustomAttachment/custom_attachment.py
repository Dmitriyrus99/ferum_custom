import frappe
from frappe.model.document import Document
from frappe import _

# Conditional import for googleapiclient, as it's an external dependency
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_DRIVE_INTEGRATION_ENABLED = True
except ImportError:
    GOOGLE_DRIVE_INTEGRATION_ENABLED = False
    frappe.log_error("google-api-python-client library not found. Google Drive integration will be disabled.", "Google Drive Integration")

class CustomAttachment(Document):
    def before_insert(self):
        if not GOOGLE_DRIVE_INTEGRATION_ENABLED:
            frappe.msgprint(_("Google Drive integration is disabled. google-api-python-client library not found."))
            return

        try:
            # Authenticate with Google Drive API using service account credentials
            # Assumes GOOGLE_APPLICATION_CREDENTIALS env var is set or key file is in default location
            # Or you might load credentials from Frappe settings
            service = build('drive', 'v3') # , credentials=your_credentials

            # For demonstration, let's assume the file content is available from a temporary path
            # In a real Frappe scenario, you'd get the file content from frappe.get_file or similar
            # For now, we'll just mock the file upload.
            # file_content_path = "/path/to/temp/uploaded_file.ext"
            # file_mimetype = "application/octet-stream"

            # Mock file upload data
            file_metadata = {'name': self.file_name, 'parents': [frappe.get_single("Ferum Settings").google_drive_folder_id]} # Assuming a setting for folder ID
            # media = MediaFileUpload(file_content_path, mimetype=file_mimetype)

            # Mock file object returned from Drive API
            mock_file_id = "mock_drive_file_id_" + frappe.generate_hash(length=10)
            mock_web_view_link = f"https://drive.google.com/file/d/{mock_file_id}/view"

            # In real implementation:
            # file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            # self.file_url = file.get('webViewLink')
            # self.file_id = file.get('id') # Store Drive File ID for easy deletion

            self.file_url = mock_web_view_link
            self.file_type = self.file_type or "application/octet-stream" # Use provided type or default
            frappe.msgprint(_(f"File {self.file_name} uploaded to Google Drive (mocked)."))

        except Exception as e:
            frappe.log_error(f"Google Drive upload failed for {self.file_name}: {e}", "Google Drive Integration Error")
            frappe.throw(_(f"Failed to upload to Google Drive: {e}"))

    def on_trash(self):
        if not GOOGLE_DRIVE_INTEGRATION_ENABLED:
            frappe.msgprint(_("Google Drive integration is disabled. google-api-python-client library not found."))
            return

        if not self.file_url: # Only attempt deletion if a file_url exists
            return

        try:
            # Authenticate with Google Drive API
            service = build('drive', 'v3') # , credentials=your_credentials

            # Extract file ID from file_url or use a stored file_id field
            # For simplicity, let's assume file_url contains the ID in a predictable way
            # In a real scenario, you would store the file_id directly in the DocType.
            file_id = self.file_url.split('/')[-2] if 'file/d/' in self.file_url else None

            if file_id:
                # In real implementation:
                # service.files().delete(fileId=file_id).execute()
                frappe.msgprint(_(f"File with ID {file_id} deleted from Google Drive (mocked)."))
            else:
                frappe.msgprint(_(f"Could not extract Google Drive File ID from URL: {self.file_url}"))

        except Exception as e:
            frappe.log_error(f"Google Drive deletion failed for {self.file_name}: {e}", "Google Drive Integration Error")
            frappe.throw(_(f"Failed to delete from Google Drive: {e}"))