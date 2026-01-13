from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frappe
from frappe import _

try:
	from google.oauth2 import service_account
	from googleapiclient.discovery import build
	from googleapiclient.http import MediaFileUpload

	_GOOGLE_DRIVE_LIBS_OK = True
except Exception:  # pragma: no cover
	service_account = None  # type: ignore[assignment]
	build = None  # type: ignore[assignment]
	MediaFileUpload = None  # type: ignore[assignment]
	_GOOGLE_DRIVE_LIBS_OK = False


_FOLDER_MIME = "application/vnd.google-apps.folder"
_DOTENV_LOADED = False


@dataclass(frozen=True)
class DriveFolder:
	id: str
	web_view_link: str


@dataclass(frozen=True)
class DriveFile:
	id: str
	web_view_link: str


def _ensure_dotenv_loaded() -> None:
	"""Load bench `.env` for long-running processes where env vars may not be passed explicitly."""
	global _DOTENV_LOADED
	if _DOTENV_LOADED:
		return
	_DOTENV_LOADED = True
	try:
		from dotenv import load_dotenv  # type: ignore
	except Exception:
		return

	for parent in Path(__file__).resolve().parents[:8]:
		candidate = parent / ".env"
		if candidate.exists():
			load_dotenv(dotenv_path=str(candidate), override=False)
			return


def _get_conf(key: str) -> str | None:
	_ensure_dotenv_loaded()
	val = frappe.conf.get(key) if hasattr(frappe, "conf") else None
	if val is None:
		val = os.getenv(key)
	if val is None:
		return None
	val = str(val).strip()
	return val or None


def service_account_key_path() -> str:
	filename = _get_conf("GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_FILENAME")
	if filename:
		return frappe.get_site_path("private", "keys", filename)

	return (
		_get_conf("google_drive_service_account_key_path")
		or _get_conf("FERUM_GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_PATH")
		or _get_conf("FERUM_GOOGLE_SERVICE_ACCOUNT_JSON")
		or _get_conf("GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_PATH")
		or frappe.get_site_path("private", "keys", "google_drive_service_account.json")
	)


def root_folder_id() -> str | None:
	return (
		_get_conf("google_drive_folder_id")
		or _get_conf("ferum_google_drive_folder_id")
		or _get_conf("FERUM_GOOGLE_DRIVE_FOLDER_ID")
		or _get_conf("FERUM_GOOGLE_DRIVE_ROOT_FOLDER_ID")
		or _get_conf("GOOGLE_DRIVE_FOLDER_ID")
	)


def is_configured() -> bool:
	if not _GOOGLE_DRIVE_LIBS_OK:
		return False
	root_id = root_folder_id()
	if not root_id:
		return False
	return Path(service_account_key_path()).exists()


def _load_service_account_json() -> dict[str, Any] | None:
	path = service_account_key_path()
	try:
		with open(path, encoding="utf-8") as f:
			data = json.load(f) or {}
	except Exception:
		return None
	if not isinstance(data, dict):
		return None
	return data


def service_account_client_email() -> str | None:
	data = _load_service_account_json() or {}
	email = str(data.get("client_email") or "").strip()
	return email or None


def service_account_project_id() -> str | None:
	data = _load_service_account_json() or {}
	project_id = str(data.get("project_id") or "").strip()
	return project_id or None


def _folder_web_link(folder_id: str) -> str:
	return f"https://drive.google.com/drive/folders/{folder_id}"


def _escape_drive_query_value(value: str) -> str:
	# Drive query uses single quotes; escape backslash and quote.
	return value.replace("\\", "\\\\").replace("'", "\\'")


def get_drive_service():
	if not _GOOGLE_DRIVE_LIBS_OK:
		frappe.throw(_("Google Drive integration is disabled (missing google api libraries)."))

	key_path = service_account_key_path()
	if not os.path.exists(key_path):
		frappe.throw(_("Google Drive service account key file not found at: {0}").format(key_path))

	credentials = service_account.Credentials.from_service_account_file(  # type: ignore[union-attr]
		key_path,
		scopes=["https://www.googleapis.com/auth/drive"],
	)
	return build("drive", "v3", credentials=credentials, cache_discovery=False)  # type: ignore[misc]


def ensure_folder(service: Any, *, name: str, parent_id: str) -> DriveFolder:
	name = (name or "").strip()
	if not name:
		raise ValueError("Folder name is empty")
	if not parent_id:
		raise ValueError("parent_id is empty")

	q = (
		f"mimeType='{_FOLDER_MIME}' and trashed=false "
		f"and name='{_escape_drive_query_value(name)}' "
		f"and '{_escape_drive_query_value(parent_id)}' in parents"
	)

	existing = (
		service.files()
		.list(q=q, spaces="drive", fields="files(id, webViewLink)", pageSize=1)
		.execute()
	)
	files = (existing or {}).get("files") or []
	if files:
		f = files[0] or {}
		fid = str(f.get("id") or "").strip()
		if not fid:
			raise ValueError("Drive API returned folder without id")
		return DriveFolder(id=fid, web_view_link=str(f.get("webViewLink") or _folder_web_link(fid)))

	created = (
		service.files()
		.create(
			body={"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]},
			fields="id,webViewLink",
		)
		.execute()
	)
	fid = str((created or {}).get("id") or "").strip()
	if not fid:
		raise ValueError("Failed to create folder in Drive (missing id)")
	return DriveFolder(id=fid, web_view_link=str((created or {}).get("webViewLink") or _folder_web_link(fid)))


def upload_file(
	service: Any,
	*,
	local_path: str,
	parent_id: str,
	name: str | None = None,
	mime_type: str | None = None,
) -> DriveFile:
	"""Upload a local file to Google Drive (simple upload)."""
	if not _GOOGLE_DRIVE_LIBS_OK or MediaFileUpload is None:
		frappe.throw(_("Google Drive integration is disabled (missing google api libraries)."))

	local_path = str(local_path or "").strip()
	parent_id = str(parent_id or "").strip()
	if not local_path:
		raise ValueError("local_path is empty")
	if not parent_id:
		raise ValueError("parent_id is empty")

	p = Path(local_path)
	if not p.exists():
		raise ValueError(f"File not found: {local_path}")

	name = (name or p.name).strip()
	mime_type = (mime_type or mimetypes.guess_type(str(p))[0] or "application/octet-stream").strip()

	uploaded = (
		service.files()
		.create(
			body={"name": name, "parents": [parent_id]},
			media_body=MediaFileUpload(str(p), mimetype=mime_type, resumable=False),  # type: ignore[misc]
			fields="id,webViewLink",
		)
		.execute()
	)
	fid = str((uploaded or {}).get("id") or "").strip()
	if not fid:
		raise ValueError("Failed to upload file to Drive (missing id)")
	return DriveFile(id=fid, web_view_link=str((uploaded or {}).get("webViewLink") or ""))


def project_folder_name(*, project_code: str, project_title: str | None) -> str:
	project_code = (project_code or "").strip()
	project_title = (project_title or "").strip()
	if project_title and project_title != project_code:
		return f"{project_code} — {project_title}".strip()
	return project_code or project_title


def site_folder_name(*, idx: int, site_name: str | None) -> str:
	site_name = (site_name or "").strip()
	prefix = f"{int(idx):02d}" if idx else ""
	return f"{prefix} {site_name}".strip() if prefix else (site_name or "")
