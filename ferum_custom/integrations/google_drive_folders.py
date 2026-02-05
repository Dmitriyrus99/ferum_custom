from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import frappe
from frappe import _

from ferum_custom.config.settings import get_settings

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


@dataclass(frozen=True)
class DriveFolder:
	id: str
	web_view_link: str


@dataclass(frozen=True)
class DriveFile:
	id: str
	web_view_link: str


def _get_conf(key: str) -> str | None:
	settings = get_settings()
	return settings.get(key)


def _looks_like_json(raw: str) -> bool:
	raw = (raw or "").lstrip()
	return raw.startswith("{") and ("client_email" in raw or "private_key" in raw)


def _ensure_service_account_file_from_json(raw_json: str) -> str:
	raw_json = (raw_json or "").strip()
	if not raw_json:
		raise ValueError("service account json is empty")

	# Validate JSON without leaking it in logs.
	try:
		payload = json.loads(raw_json) or {}
	except Exception as exc:
		raise ValueError("invalid service account json") from exc
	if not isinstance(payload, dict) or not payload.get("client_email"):
		raise ValueError("invalid service account json structure")

	keys_dir = Path(frappe.get_site_path("private", "keys"))
	keys_dir.mkdir(parents=True, exist_ok=True)
	path = keys_dir / "google_drive_service_account.json"

	# Avoid rewriting if content already matches.
	try:
		current = path.read_text(encoding="utf-8")
	except Exception:
		current = None
	if current is None or current.strip() != raw_json:
		path.write_text(raw_json + "\n", encoding="utf-8")
		try:
			os.chmod(path, 0o600)
		except Exception:
			pass

	return str(path)


def service_account_key_path() -> str:
	filename = _get_conf("GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_FILENAME")
	if filename:
		return frappe.get_site_path("private", "keys", filename)

	raw = (
		_get_conf("FERUM_GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_PATH")
		or _get_conf("FERUM_GOOGLE_SERVICE_ACCOUNT_JSON")
		or _get_conf("GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_PATH")
		or _get_conf("google_drive_service_account_key_path")
	)
	raw = str(raw or "").strip()
	if raw and _looks_like_json(raw):
		return _ensure_service_account_file_from_json(raw)
	if raw:
		return raw

	return frappe.get_site_path("private", "keys", "google_drive_service_account.json")


def root_folder_id() -> str | None:
	return (
		_get_conf("FERUM_GOOGLE_DRIVE_ROOT_FOLDER_ID")
		or _get_conf("FERUM_GOOGLE_DRIVE_FOLDER_ID")
		or _get_conf("GOOGLE_DRIVE_FOLDER_ID")
		or _get_conf("google_drive_folder_id")
		or _get_conf("ferum_google_drive_folder_id")
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


def get_drive_file(
	service: Any, *, file_id: str, fields: str = "id,name,mimeType,parents,webViewLink"
) -> dict[str, Any]:
	file_id = str(file_id or "").strip()
	if not file_id:
		raise ValueError("file_id is empty")
	return service.files().get(fileId=file_id, fields=fields, supportsAllDrives=True).execute()


def update_drive_file(
	service: Any,
	*,
	file_id: str,
	body: dict[str, Any] | None = None,
	add_parents: str | None = None,
	remove_parents: str | None = None,
	fields: str = "id,name,mimeType,parents,webViewLink",
) -> dict[str, Any]:
	file_id = str(file_id or "").strip()
	if not file_id:
		raise ValueError("file_id is empty")

	return (
		service.files()
		.update(
			fileId=file_id,
			body=body or {},
			addParents=add_parents,
			removeParents=remove_parents,
			fields=fields,
			supportsAllDrives=True,
		)
		.execute()
	)


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
		.list(
			q=q,
			spaces="drive",
			fields="files(id, webViewLink)",
			pageSize=1,
			includeItemsFromAllDrives=True,
			supportsAllDrives=True,
		)
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
			supportsAllDrives=True,
		)
		.execute()
	)
	fid = str((created or {}).get("id") or "").strip()
	if not fid:
		raise ValueError("Failed to create folder in Drive (missing id)")
	return DriveFolder(id=fid, web_view_link=str((created or {}).get("webViewLink") or _folder_web_link(fid)))


def find_folder(service: Any, *, name: str, parent_id: str) -> DriveFolder | None:
	"""Find a folder by exact name under a parent folder (no creation)."""
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
		.list(
			q=q,
			spaces="drive",
			fields="files(id, webViewLink)",
			pageSize=1,
			includeItemsFromAllDrives=True,
			supportsAllDrives=True,
		)
		.execute()
	)
	files = (existing or {}).get("files") or []
	if not files:
		return None

	f = files[0] or {}
	fid = str(f.get("id") or "").strip()
	if not fid:
		return None
	return DriveFolder(id=fid, web_view_link=str(f.get("webViewLink") or _folder_web_link(fid)))


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
			supportsAllDrives=True,
		)
		.execute()
	)
	fid = str((uploaded or {}).get("id") or "").strip()
	if not fid:
		raise ValueError("Failed to upload file to Drive (missing id)")
	return DriveFile(id=fid, web_view_link=str((uploaded or {}).get("webViewLink") or ""))


def upsert_json_file(
	service: Any,
	*,
	parent_id: str,
	name: str,
	payload: dict[str, Any],
	indent: int = 2,
) -> DriveFile:
	"""Create or update a JSON file under a Drive folder (by exact name)."""
	parent_id = str(parent_id or "").strip()
	name = str(name or "").strip()
	if not parent_id:
		raise ValueError("parent_id is empty")
	if not name:
		raise ValueError("name is empty")
	if not _GOOGLE_DRIVE_LIBS_OK or MediaFileUpload is None:
		frappe.throw(_("Google Drive integration is disabled (missing google api libraries)."))

	q = (
		"trashed=false "
		f"and name='{_escape_drive_query_value(name)}' "
		f"and '{_escape_drive_query_value(parent_id)}' in parents"
	)
	existing = (
		service.files()
		.list(
			q=q,
			spaces="drive",
			fields="files(id, webViewLink)",
			pageSize=1,
			includeItemsFromAllDrives=True,
			supportsAllDrives=True,
		)
		.execute()
	)
	files = (existing or {}).get("files") or []
	existing_id = str((files[0] or {}).get("id") or "").strip() if files else ""

	with NamedTemporaryFile(prefix="drive_", suffix=".json", delete=False) as tmp:
		tmp.write(json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True).encode("utf-8"))
		tmp.flush()
		tmp_path = tmp.name

	try:
		media = MediaFileUpload(tmp_path, mimetype="application/json", resumable=False)  # type: ignore[misc]
		if existing_id:
			updated = (
				service.files()
				.update(
					fileId=existing_id,
					media_body=media,
					fields="id,webViewLink",
					supportsAllDrives=True,
				)
				.execute()
			)
			fid = str((updated or {}).get("id") or existing_id).strip()
			return DriveFile(id=fid, web_view_link=str((updated or {}).get("webViewLink") or ""))

		created = (
			service.files()
			.create(
				body={"name": name, "parents": [parent_id]},
				media_body=media,
				fields="id,webViewLink",
				supportsAllDrives=True,
			)
			.execute()
		)
		fid = str((created or {}).get("id") or "").strip()
		if not fid:
			raise ValueError("Failed to create JSON file in Drive (missing id)")
		return DriveFile(id=fid, web_view_link=str((created or {}).get("webViewLink") or ""))
	finally:
		try:
			os.remove(tmp_path)
		except Exception:
			pass


def project_folder_name(*, project_code: str, project_title: str | None) -> str:
	# Deterministic folder key: use Project ID (name) only.
	project_code = (project_code or "").strip()
	return project_code or (project_title or "").strip()


def site_folder_name(*, idx: int, site_name: str | None) -> str:
	site_name = (site_name or "").strip()
	prefix = f"{int(idx):02d}" if idx else ""
	return f"{prefix} {site_name}".strip() if prefix else (site_name or "")
