from __future__ import annotations

import json
import re

import frappe
from frappe import _

from ferum_custom.integrations.google_drive_folders import (
	ensure_folder,
	get_drive_service,
	project_folder_name,
	root_folder_id,
	service_account_client_email,
	service_account_project_id,
	site_folder_name,
)


def _has_role(role: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	try:
		return role in set(frappe.get_roles(user))
	except Exception:
		return False


def _require_drive_manager() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if _has_role("System Manager"):
		return
	if _has_role("Projects Manager") or _has_role("Project Manager"):
		return
	if _has_role("Office Manager") or _has_role("Ferum Office Manager"):
		return
	frappe.throw(_("Not permitted"), frappe.PermissionError)


def _extract_google_project_number(text: str) -> str | None:
	# Example: "... Enable it by visiting ...?project=74300019080 ..."
	m = re.search(r"project[=\\s]+(\\d{6,})", text or "")
	return m.group(1) if m else None


def _google_http_error_details(exc: Exception) -> tuple[int | None, str | None, str | None, str]:
	status: int | None = None
	reason: str | None = None
	message: str | None = None

	content_text = ""
	content = getattr(exc, "content", None)
	if isinstance(content, (bytes, bytearray)):
		content_text = content.decode("utf-8", "replace")
	elif content is not None:
		content_text = str(content)

	try:
		payload = json.loads(content_text) if content_text else {}
	except Exception:
		payload = {}

	if isinstance(payload, dict):
		err = payload.get("error") if isinstance(payload.get("error"), dict) else {}
		if isinstance(err, dict):
			try:
				status = int(err.get("code")) if err.get("code") is not None else None
			except Exception:
				status = None
			message = str(err.get("message") or "") or None

			errors = err.get("errors") if isinstance(err.get("errors"), list) else []
			if errors and isinstance(errors[0], dict):
				reason = str(errors[0].get("reason") or "") or None

	# Fall back to response status if available.
	resp = getattr(exc, "resp", None)
	if status is None and resp is not None:
		try:
			status = int(getattr(resp, "status", None))
		except Exception:
			status = None

	return status, reason, message, content_text


def _friendly_drive_error(exc: Exception) -> str:
	sa_email = service_account_client_email()
	sa_project_id = service_account_project_id()
	root_id = root_folder_id()

	# Try to detect googleapiclient HttpError without hard import requirement.
	try:
		from googleapiclient.errors import HttpError  # type: ignore
	except Exception:  # pragma: no cover
		HttpError = None  # type: ignore

	if HttpError and isinstance(exc, HttpError):  # type: ignore[arg-type]
		status, reason, message, content_text = _google_http_error_details(exc)
		text = " ".join([str(message or ""), content_text]).strip()

		if status == 403 and (reason == "accessNotConfigured" or "accessNotConfigured" in text):
			project_number = _extract_google_project_number(text)
			project_hint = sa_project_id or project_number or "?"
			return (
				"Google Drive API отключён/не включён для проекта Google Cloud. "
				f"Включи «Google Drive API» (project: {project_hint}), подожди 5–10 минут и повтори. "
				+ (f"Service account: {sa_email}." if sa_email else "")
			)

		if status == 404:
			return (
				"Корневая папка Google Drive не найдена или нет доступа. "
				+ (f"folder_id: {root_id}. " if root_id else "")
				+ (f"Service account: {sa_email}. " if sa_email else "")
				+ "Проверь ID папки и расшарь её на service account с правами Editor."
			)

		if status == 403:
			return (
				"Нет доступа к корневой папке Google Drive. "
				+ (f"folder_id: {root_id}. " if root_id else "")
				+ (f"Service account: {sa_email}. " if sa_email else "")
				+ "Расшарь папку на service account (Editor) и повтори."
			)

		return f"Ошибка Google Drive (HTTP {status or '??'}): {message or str(exc)}"

	# Network / transport issues (DNS, no route, etc.)
	try:
		from google.auth.exceptions import TransportError  # type: ignore
	except Exception:  # pragma: no cover
		TransportError = None  # type: ignore

	if TransportError and isinstance(exc, TransportError):  # type: ignore[arg-type]
		return (
			"Ошибка сети при обращении к Google Drive API. "
			"Проверь доступ сервера к интернету/DNS и повтори."
		)

	# Default fallback.
	return f"Ошибка при создании папок Google Drive: {str(exc) or 'unknown error'}"


@frappe.whitelist(methods=["POST"])
def ensure_drive_folders(project: str) -> dict:
	"""Create (or reuse) Google Drive folders for a Project and its objects (Project Sites).

	Stores folder links in:
	- Project.drive_folder_url
	- Project Site.drive_folder_url (child rows), if the field exists

	Requires a configured service account key + root folder id.
	"""
	_require_drive_manager()
	project = (project or "").strip()
	if not project:
		frappe.throw(_("Missing project."))
	if not frappe.db.exists("Project", project):
		frappe.throw(_("Project not found."))

	root_id = (root_folder_id() or "").strip()
	if not root_id:
		frappe.throw(_("Google Drive root folder is not configured."))

	try:
		service = get_drive_service()
		doc = frappe.get_doc("Project", project)
		meta = doc.meta
		title = str(getattr(doc, "project_name", "") or "").strip() if meta.has_field("project_name") else ""

		proj_folder = ensure_folder(
			service,
			name=project_folder_name(project_code=project, project_title=title),
			parent_id=root_id,
		)
	except Exception as exc:
		frappe.log_error(title="Ferum: Google Drive folders", message=frappe.get_traceback())
		frappe.throw(_friendly_drive_error(exc))

	# Update project folder url without triggering Project validate gates.
	if meta.has_field("drive_folder_url") and frappe.db.has_column("Project", "drive_folder_url"):
		frappe.db.set_value("Project", project, "drive_folder_url", proj_folder.web_view_link, update_modified=True)

	# Create folders for each Project Site.
	site_results: list[dict] = []
	for row in doc.get("project_sites") or []:
		row_name = str(getattr(row, "name", "") or "").strip()
		site_name = str(getattr(row, "site_name", "") or "").strip()
		idx = int(getattr(row, "idx", 0) or 0)
		if not row_name or not site_name:
			continue
		try:
			folder = ensure_folder(
				service,
				name=site_folder_name(idx=idx, site_name=site_name),
				parent_id=proj_folder.id,
			)
		except Exception as exc:
			frappe.log_error(title="Ferum: Google Drive folders", message=frappe.get_traceback())
			frappe.throw(_friendly_drive_error(exc))
		site_results.append({"row": row_name, "site_name": site_name, "url": folder.web_view_link})
		# Update child row without saving the whole Project doc.
		if frappe.db.has_column("Project Site", "drive_folder_url"):
			frappe.db.set_value("Project Site", row_name, "drive_folder_url", folder.web_view_link, update_modified=False)

	return {"ok": True, "project": project, "project_folder_url": proj_folder.web_view_link, "sites": site_results}
