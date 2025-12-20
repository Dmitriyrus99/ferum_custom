import os

import frappe
from frappe import _
from frappe.model.document import Document

# Conditional import for google-api-python-client and google-auth
try:
	from google.oauth2 import service_account
	from googleapiclient.discovery import build

	GOOGLE_DRIVE_INTEGRATION_ENABLED = True
except ImportError:
	GOOGLE_DRIVE_INTEGRATION_ENABLED = False
	frappe.log_error(
		"Google API Python Client libraries not found. Google Drive integration will be disabled.",
		"Google Drive Integration",
	)


class CustomAttachment(Document):
	def validate(self):
		if self.file_url and not self.google_drive_file_id and GOOGLE_DRIVE_INTEGRATION_ENABLED:
			# If a file is attached (file_url is set) and not yet uploaded to Drive
			self.upload_to_google_drive()

	def on_trash(self):
		if self.google_drive_file_id and GOOGLE_DRIVE_INTEGRATION_ENABLED:
			self.delete_from_google_drive()

	def get_drive_service(self):
		if not GOOGLE_DRIVE_INTEGRATION_ENABLED:
			frappe.throw(_("Google Drive integration is not enabled. Missing required libraries."))

		try:
			# Assuming the path to the service account key file is stored in site_config.json
			# or a custom DocType setting, e.g., frappe.conf.google_drive_service_account_key_path
			# For development, you might place it in the app folder or a secure location.
			key_file_path = frappe.get_site_path("private", "keys", "google_drive_service_account.json")
			if not os.path.exists(key_file_path):
				frappe.throw(_("Google Drive service account key file not found at: ") + key_file_path)

			credentials = service_account.Credentials.from_service_account_file(
				key_file_path, scopes=["https://www.googleapis.com/auth/drive"]
			)
			return build("drive", "v3", credentials=credentials)
		except Exception as e:
			frappe.log_error(f"Failed to get Google Drive service: {e}", "Google Drive Integration Error")
			frappe.throw(_(f"Failed to initialize Google Drive service: {e}"))

	def upload_to_google_drive(self):
		if not self.file_url:
			return

		service = self.get_drive_service()
		file_path = frappe.get_site_path("public", self.file_url.lstrip("/"))  # Assuming public files for now

		# If the file is private, adjust the path accordingly
		if "/private/files/" in self.file_url:
			file_path = frappe.get_site_path("private", self.file_url.split("/private/files/")[1])

		if not os.path.exists(file_path):
			frappe.throw(_("File not found on server: ") + file_path)

		file_metadata = {
			"name": self.file_name or os.path.basename(file_path),
			"parents": [frappe.conf.google_drive_folder_id],  # Parent folder ID from site_config
		}
		media = {
			"body": open(file_path, "rb"),
			"mimeType": self.file_url.split(".")[-1],  # Simple mime type guess
		}

		try:
			file = (
				service.files()
				.create(body=file_metadata, media_body=media, fields="id, webViewLink")
				.execute()
			)
			self.google_drive_file_id = file.get("id")
			self.file_url = file.get("webViewLink")  # Update file_url to Google Drive link
			frappe.msgprint(_(f"File {self.file_name} uploaded to Google Drive."))
		except Exception as e:
			frappe.log_error(
				f"Failed to upload file {self.file_name} to Google Drive: {e}",
				"Google Drive Integration Error",
			)
			frappe.throw(_(f"Failed to upload file to Google Drive: {e}"))

	def delete_from_google_drive(self):
		if not self.google_drive_file_id:
			return

		service = self.get_drive_service()
		try:
			service.files().delete(fileId=self.google_drive_file_id).execute()
			frappe.msgprint(_(f"File {self.file_name} deleted from Google Drive."))
		except Exception as e:
			frappe.log_error(
				f"Failed to delete file {self.file_name} from Google Drive: {e}",
				"Google Drive Integration Error",
			)
			frappe.throw(_(f"Failed to delete file from Google Drive: {e}"))
