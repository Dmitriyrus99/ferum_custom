from __future__ import annotations

import mimetypes
from pathlib import Path

import frappe
from frappe import _
from frappe.model.document import Document

from ferum_custom.integrations.google_drive_folders import get_drive_service, root_folder_id

try:
	from google.oauth2 import service_account
	from googleapiclient.discovery import build
	from googleapiclient.http import MediaFileUpload

	GOOGLE_DRIVE_INTEGRATION_ENABLED = True
except Exception:
	service_account = None  # type: ignore[assignment]
	build = None  # type: ignore[assignment]
	MediaFileUpload = None  # type: ignore[assignment]
	GOOGLE_DRIVE_INTEGRATION_ENABLED = False


def _drive_folder_id() -> str | None:
	# Keep legacy keys supported via unified settings layer.
	return root_folder_id()


def _resolve_file_path(file_url: str) -> Path:
	file_url = (file_url or "").strip()
	if not file_url:
		raise ValueError("file_url is empty")

	# Already a remote URL (likely Drive link) – nothing to upload.
	if file_url.startswith(("http://", "https://")):
		raise ValueError("file_url points to remote URL")

	# Absolute filesystem path
	p = Path(file_url)
	if p.is_absolute():
		return p

	if file_url.startswith("/private/files/"):
		return Path(frappe.get_site_path("private", "files", file_url.split("/private/files/", 1)[1]))

	if file_url.startswith("/files/"):
		return Path(frappe.get_site_path("public", "files", file_url.split("/files/", 1)[1]))

	if file_url.startswith("/"):
		return Path(frappe.get_site_path("public", file_url.lstrip("/")))

	# Relative path: treat as under public
	return Path(frappe.get_site_path("public", file_url))


class CustomAttachment(Document):
	def validate(self):
		if not GOOGLE_DRIVE_INTEGRATION_ENABLED:
			return

		if getattr(self, "file_url", None) and not getattr(self, "drive_file_id", None):
			self.upload_to_google_drive()

	def on_trash(self):
		if GOOGLE_DRIVE_INTEGRATION_ENABLED and getattr(self, "drive_file_id", None):
			self.delete_from_google_drive()

	def _get_drive_service(self):
		return get_drive_service()

	def upload_to_google_drive(self):
		file_url = getattr(self, "file_url", None)
		if not file_url:
			return

		try:
			path = _resolve_file_path(str(file_url))
		except ValueError:
			# Remote URL or invalid path - nothing to upload.
			return

		if not path.exists():
			frappe.throw(_("File not found on server: {0}").format(str(path)))

		service = self._get_drive_service()

		folder_id = _drive_folder_id()
		file_name = getattr(self, "file_name", None) or path.name
		mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

		file_metadata: dict[str, object] = {"name": file_name}
		if folder_id:
			file_metadata["parents"] = [folder_id]

		media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)  # type: ignore[misc]
		try:
			uploaded = (
				service.files()
				.create(body=file_metadata, media_body=media, fields="id,webViewLink")
				.execute()
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Google Drive Integration Error")
			frappe.throw(_("Failed to upload file to Google Drive."))

		self.drive_file_id = uploaded.get("id")
		self.drive_web_link = uploaded.get("webViewLink")
		if hasattr(self, "file_type") and not getattr(self, "file_type", None):
			self.file_type = path.suffix.lstrip(".")

		frappe.msgprint(_("File uploaded to Google Drive."))

	def delete_from_google_drive(self):
		drive_file_id = getattr(self, "drive_file_id", None)
		if not drive_file_id:
			return

		service = self._get_drive_service()
		try:
			service.files().delete(fileId=str(drive_file_id)).execute()
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Google Drive Integration Error")
			frappe.throw(_("Failed to delete file from Google Drive."))

		frappe.msgprint(_("File deleted from Google Drive."))
