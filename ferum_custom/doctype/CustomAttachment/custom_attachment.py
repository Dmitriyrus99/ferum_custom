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

        # --- START Google Drive Upload Implementation --- #
        # This section needs to be replaced with actual Google Drive API calls.
        # You will need to get the actual file content from somewhere.
        # In Frappe, files are usually uploaded to the server first, then processed.
        # You might need to add a temporary file path or base64 content to this DocType
        # or retrieve it from Frappe's file storage.

        try:
            # 1. Authenticate with Google Drive API
            #    Ensure your service account JSON key file is accessible and configured
            #    (e.g., via GOOGLE_APPLICATION_CREDENTIALS env var or Frappe settings).
            service = build('drive', 'v3') # , credentials=your_credentials

            # 2. Prepare file metadata and content
            #    Example: file_metadata = {'name': self.file_name, 'parents': ['YOUR_DRIVE_FOLDER_ID']}
            #    Example: media = MediaFileUpload('path/to/local/file', mimetype=self.file_type)

            # 3. Execute the upload
            #    file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()

            # 4. Store the Google Drive file ID and webViewLink
            #    self.file_url = file.get('webViewLink')
            #    self.google_drive_file_id = file.get('id') # Consider adding this field to DocType

            # Placeholder for successful upload
            self.file_url = f"https://drive.google.com/mock_file_id/{frappe.generate_hash(length=10)}/view"
            self.file_type = self.file_type or "application/octet-stream"
            frappe.msgprint(_(f"File {self.file_name} uploaded to Google Drive (placeholder)."))

        except Exception as e:
            frappe.log_error(f"Google Drive upload failed for {self.file_name}: {e}", "Google Drive Integration Error")
            frappe.throw(_(f"Failed to upload to Google Drive: {e}"))
        # --- END Google Drive Upload Implementation --- #

    def on_trash(self):
        if not GOOGLE_DRIVE_INTEGRATION_ENABLED:
            frappe.msgprint(_("Google Drive integration is disabled. google-api-python-client library not found."))
            return

        if not self.file_url: # Only attempt deletion if a file_url exists
            return

        # --- START Google Drive Deletion Implementation --- #
        # This section needs to be replaced with actual Google Drive API calls.
        # You will need the Google Drive File ID to delete the file.
        # It's best to store the Google Drive File ID directly in the DocType.

        try:
            # 1. Authenticate with Google Drive API
            service = build('drive', 'v3') # , credentials=your_credentials

            # 2. Extract file ID (if not stored directly) or use self.google_drive_file_id
            file_id = self.file_url.split('/')[-2] if 'file/d/' in self.file_url else None

            if file_id:
                # 3. Execute the deletion
                # service.files().delete(fileId=file_id).execute()
                frappe.msgprint(_(f"File with ID {file_id} deleted from Google Drive (placeholder)."))
            else:
                frappe.msgprint(_(f"Could not extract Google Drive File ID from URL: {self.file_url}"))

        except Exception as e:
            frappe.log_error(f"Google Drive deletion failed for {self.file_name}: {e}", "Google Drive Integration Error")
            frappe.throw(_(f"Failed to delete from Google Drive: {e}"))
        # --- END Google Drive Deletion Implementation --- #
