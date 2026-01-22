from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from ferum_custom.integrations.google_drive_folders import (
	DriveFolder,
	ensure_folder,
	find_folder,
	get_drive_file,
	get_drive_service,
	root_folder_id,
	service_account_client_email,
	service_account_project_id,
	update_drive_file,
	upsert_json_file,
)

_FOLDER_MIME = "application/vnd.google-apps.folder"


def _ensure_folder_migrating_name(
	service,
	*,
	name: str,
	parent_id: str,
	legacy_names: list[str] | tuple[str, ...] = (),
) -> DriveFolder:
	"""Ensure folder exists; if a legacy name exists, rename it in-place to `name`.

	Returns the folder id + webViewLink. Folder IDs are preserved on rename.
	"""
	name = (name or "").strip()
	parent_id = str(parent_id or "").strip()
	if not name:
		raise ValueError("Folder name is empty")
	if not parent_id:
		raise ValueError("parent_id is empty")

	existing = find_folder(service, name=name, parent_id=parent_id)
	if existing:
		return existing

	for legacy in legacy_names or []:
		legacy = str(legacy or "").strip()
		if not legacy:
			continue
		found = find_folder(service, name=legacy, parent_id=parent_id)
		if not found:
			continue
		updated = update_drive_file(service, file_id=found.id, body={"name": name})
		fid = str((updated or {}).get("id") or found.id).strip()
		link = str((updated or {}).get("webViewLink") or found.web_view_link).strip()
		return DriveFolder(id=fid, web_view_link=link)

	return ensure_folder(service, name=name, parent_id=parent_id)


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


def _drive_folder_id_from_url(url: str | None) -> str | None:
	url = str(url or "").strip()
	if not url:
		return None
	m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
	return m.group(1) if m else None


def _safe_folder_component(value: str) -> str:
	value = str(value or "").strip()
	value = re.sub(r"[\\/\0<>:\"|?*]+", "_", value)
	value = re.sub(r"\s+", " ", value).strip()
	return value[:120] or "_"


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


def _get_or_create_project_root_folder(*, service, project_doc, root_id: str) -> tuple[str, str]:
	"""Return (folder_id, web_view_link) for the Project root folder.

	Uses existing Project.drive_folder_url if present (and accessible), otherwise creates a new folder.
	Ensures the folder is located under the deterministic path:
	  <root>/<01_ОРГАНИЗАЦИЯ_<company_id>>/01_ПРОЕКТЫ/<PROJECT_ID>
	"""

	project_name = str(project_doc.name or "").strip()
	if not project_name:
		raise ValueError("project name is empty")

	company = ""
	if project_doc.meta.has_field("company"):
		company = str(getattr(project_doc, "company", "") or "").strip()

	company_key = _safe_folder_component(company or "DEFAULT")
	company_folder_name = f"01_ОРГАНИЗАЦИЯ_{company_key}"
	company_folder = _ensure_folder_migrating_name(
		service,
		name=company_folder_name,
		legacy_names=(f"01_COMPANY_{company_key}",),
		parent_id=root_id,
	)
	projects_folder = _ensure_folder_migrating_name(
		service,
		name="01_ПРОЕКТЫ",
		legacy_names=("01_PROJECTS",),
		parent_id=company_folder.id,
	)

	desired_parent_id = projects_folder.id
	desired_name = _safe_folder_component(project_name)

	existing_id = None
	if project_doc.meta.has_field("drive_folder_url") and frappe.db.has_column("Project", "drive_folder_url"):
		existing_id = _drive_folder_id_from_url(getattr(project_doc, "drive_folder_url", None))

	if existing_id:
		try:
			info = get_drive_file(service, file_id=existing_id)
		except Exception:
			info = None

		if isinstance(info, dict) and str(info.get("mimeType") or "") == _FOLDER_MIME:
			parents = info.get("parents") if isinstance(info.get("parents"), list) else []
			parents = [str(p).strip() for p in parents if p]
			body = {}
			if str(info.get("name") or "") != desired_name:
				body["name"] = desired_name

			remove_parents = ",".join([p for p in parents if p and p != desired_parent_id]) if parents else None
			add_parents = desired_parent_id if desired_parent_id not in parents else None

			if body or add_parents or remove_parents:
				info = update_drive_file(
					service,
					file_id=existing_id,
					body=body or None,
					add_parents=add_parents,
					remove_parents=remove_parents,
				)

			folder_id = str(info.get("id") or existing_id).strip()
			web_link = str(info.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder_id}").strip()
			return folder_id, web_link

	# No existing folder or it's not accessible/valid -> create / reuse by name under deterministic parent.
	proj_folder = ensure_folder(service, name=desired_name, parent_id=desired_parent_id)
	return proj_folder.id, proj_folder.web_view_link


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
		project_folder_id, project_folder_url = _get_or_create_project_root_folder(
			service=service,
			project_doc=doc,
			root_id=root_id,
		)

		# Create deterministic subfolders.
		meta_folder = _ensure_folder_migrating_name(
			service, name="00_МЕТА", legacy_names=("00_META",), parent_id=project_folder_id
		)
		documents_folder = _ensure_folder_migrating_name(
			service, name="01_ДОКУМЕНТЫ", legacy_names=("01_DOCUMENTS",), parent_id=project_folder_id
		)
		objects_folder = _ensure_folder_migrating_name(
			service, name="02_ОБЪЕКТЫ", legacy_names=("02_OBJECTS",), parent_id=project_folder_id
		)
		_ensure_folder_migrating_name(
			service, name="99_АРХИВ", legacy_names=("99_ARCHIVE",), parent_id=project_folder_id
		)

		# Documents sub-tree (fixed categories).
		contracts_customer = _ensure_folder_migrating_name(
			service,
			name="01_ДОГОВОРЫ_ЗАКАЗЧИК",
			legacy_names=("01_CONTRACTS_CUSTOMER",),
			parent_id=documents_folder.id,
		)
		_ensure_folder_migrating_name(
			service,
			name="02_ДОГОВОРЫ_ПОДРЯДЧИКИ",
			legacy_names=("02_CONTRACTS_CONTRACTORS",),
			parent_id=documents_folder.id,
		)
		_ensure_folder_migrating_name(
			service,
			name="03_УДОСТОВЕРЕНИЯ_И_РАЗРЕШЕНИЯ",
			legacy_names=("03_COMPLIANCE",),
			parent_id=documents_folder.id,
		)
		_ensure_folder_migrating_name(
			service,
			name="04_ЗАКРЫВАЮЩИЕ_ДОКУМЕНТЫ",
			legacy_names=("04_CLOSING",),
			parent_id=documents_folder.id,
		)
		corr = _ensure_folder_migrating_name(
			service,
			name="05_КОРРЕСПОНДЕНЦИЯ",
			legacy_names=("05_CORRESPONDENCE",),
			parent_id=documents_folder.id,
		)
		_ensure_folder_migrating_name(service, name="01_ВХОДЯЩИЕ", legacy_names=("01_IN",), parent_id=corr.id)
		_ensure_folder_migrating_name(service, name="02_ИСХОДЯЩИЕ", legacy_names=("02_OUT",), parent_id=corr.id)
		_ensure_folder_migrating_name(
			service, name="03_ВНУТРЕННИЕ", legacy_names=("03_INTERNAL",), parent_id=corr.id
		)
		_ensure_folder_migrating_name(
			service,
			name="06_СЛУЖЕБНЫЕ_ДОКУМЕНТЫ",
			legacy_names=("06_INTERNAL_DOCS",),
			parent_id=documents_folder.id,
		)
		_ensure_folder_migrating_name(
			service,
			name="99_НЕРАЗОБРАННОЕ",
			legacy_names=("99_UNSORTED",),
			parent_id=documents_folder.id,
		)

		# Keep meta folder referenced (reserved for future: project.json).
		_ = meta_folder
		_ = contracts_customer
	except Exception as exc:
		frappe.log_error(title="Ferum: Google Drive folders", message=frappe.get_traceback())
		frappe.throw(_friendly_drive_error(exc))

	# Update project folder url without triggering Project validate gates.
	if meta.has_field("drive_folder_url") and frappe.db.has_column("Project", "drive_folder_url"):
		frappe.db.set_value("Project", project, "drive_folder_url", project_folder_url, update_modified=True)

	# Create folders for each Project Site.
	site_results: list[dict] = []
	for row in doc.get("project_sites") or []:
		row_name = str(getattr(row, "name", "") or "").strip()
		site_name = str(getattr(row, "site_name", "") or "").strip()
		if not row_name or not site_name:
			continue
		try:
			# Site folder name is stable (child row ID), not user input.
			desired_site_name = _safe_folder_component(row_name)
			existing_site_id = _drive_folder_id_from_url(getattr(row, "drive_folder_url", None))

			if existing_site_id:
				info = None
				try:
					info = get_drive_file(service, file_id=existing_site_id)
				except Exception:
					info = None

				if isinstance(info, dict) and str(info.get("mimeType") or "") == _FOLDER_MIME:
					parents = info.get("parents") if isinstance(info.get("parents"), list) else []
					parents = [str(p).strip() for p in parents if p]
					body = {}
					if str(info.get("name") or "") != desired_site_name:
						body["name"] = desired_site_name
					remove_parents = ",".join([p for p in parents if p and p != objects_folder.id]) if parents else None
					add_parents = objects_folder.id if objects_folder.id not in parents else None
					if body or add_parents or remove_parents:
						info = update_drive_file(
							service,
							file_id=existing_site_id,
							body=body or None,
							add_parents=add_parents,
							remove_parents=remove_parents,
						)

					folder_id = str(info.get("id") or existing_site_id).strip()
					web_link = str(info.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder_id}").strip()
					folder = DriveFolder(id=folder_id, web_view_link=web_link)
				else:
					folder = ensure_folder(service, name=desired_site_name, parent_id=objects_folder.id)
			else:
				folder = ensure_folder(service, name=desired_site_name, parent_id=objects_folder.id)

			# Standard per-object subfolders
			_ensure_folder_migrating_name(
				service, name="01_ОБСЛЕДОВАНИЕ", legacy_names=("01_SURVEY",), parent_id=folder.id
			)
			_ensure_folder_migrating_name(
				service, name="02_ЗАЯВКИ", legacy_names=("02_SERVICE_REQUESTS",), parent_id=folder.id
			)
		except Exception as exc:
			frappe.log_error(title="Ferum: Google Drive folders", message=frappe.get_traceback())
			frappe.throw(_friendly_drive_error(exc))
		site_results.append({"row": row_name, "site_name": site_name, "url": folder.web_view_link})
		# Update child row without saving the whole Project doc.
		if frappe.db.has_column("Project Site", "drive_folder_url"):
			frappe.db.set_value("Project Site", row_name, "drive_folder_url", folder.web_view_link, update_modified=False)

	# Best-effort: keep project metadata snapshot inside Drive.
	try:
		project_title = ""
		for key in ("project_name", "title", "project_title"):
			if doc.meta.has_field(key):
				project_title = str(getattr(doc, key, "") or "").strip()
				if project_title:
					break

		customer = str(getattr(doc, "customer", "") or "").strip() if doc.meta.has_field("customer") else ""
		contract = str(getattr(doc, "contract", "") or "").strip() if doc.meta.has_field("contract") else ""
		payload = {
			"project": {
				"id": str(doc.name),
				"title": project_title or None,
				"company": str(getattr(doc, "company", "") or "").strip() if doc.meta.has_field("company") else None,
				"customer": customer or None,
				"contract": contract or None,
			},
			"drive": {
				"project_folder_url": project_folder_url,
				"generated_at": now_datetime().isoformat(),
				"structure_version": "ru_v1",
			},
			"objects": site_results,
		}
		upsert_json_file(service, parent_id=meta_folder.id, name="project.json", payload=payload)
	except Exception:
		frappe.log_error(title="Ferum: Google Drive project.json", message=frappe.get_traceback())

	return {
		"ok": True,
		"project": project,
		"project_folder_url": project_folder_url,
		"sites": site_results,
	}


@frappe.whitelist(methods=["POST"])
def ensure_drive_folders_bulk(
	projects: list[str] | None = None,
	*,
	company: str | None = None,
	limit: int = 50,
) -> dict:
	"""Best-effort bulk creation/rename of Google Drive folders for Projects.

	Intended for admin use (may take long). Collects per-project errors without failing the whole run.
	"""
	_require_drive_manager()

	project_list: list[str] = []
	if projects:
		project_list = [str(p or "").strip() for p in projects if str(p or "").strip()]
	else:
		filters = {}
		if company:
			filters["company"] = str(company).strip()
		project_list = frappe.get_all("Project", filters=filters, pluck="name", limit=int(limit) if limit else 0)  # type: ignore[assignment]

	results: list[dict] = []
	for p in project_list:
		try:
			r = ensure_drive_folders(p)
			results.append(
				{
					"project": p,
					"ok": True,
					"project_folder_url": r.get("project_folder_url"),
				}
			)
		except Exception as exc:
			results.append({"project": p, "ok": False, "error": str(exc)})

	return {"ok": True, "count": len(results), "results": results}
