from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import now_datetime

from ferum_custom.api.project_drive import ensure_drive_folders
from ferum_custom.integrations.google_drive_folders import ensure_folder, get_drive_service, upload_file
from ferum_custom.security.project_access import user_has_project_access
from ferum_custom.services.contract_project_sync import get_project_for_contract
from ferum_custom.services.project_documents_config import (
	ATTACHED_TO_FIELD,
	CLIENT_ALLOWED_TYPES,
	DOC_TYPES,
	UPLOAD_ROLES,
)


def _has_any_role(user: str, roles: set[str]) -> bool:
	try:
		user_roles = set(frappe.get_roles(user) or [])
	except Exception:
		user_roles = set()
	return bool(user_roles.intersection(roles))


def _is_client_user(user: str) -> bool:
	try:
		return "Client" in set(frappe.get_roles(user) or [])
	except Exception:
		return False


def _drive_folder_id_from_url(url: str | None) -> str | None:
	url = str(url or "").strip()
	if not url:
		return None
	m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
	return m.group(1) if m else None


def _safe_filename(name: str) -> str:
	name = (name or "").strip().replace("\n", " ").replace("\r", " ")
	name = re.sub(r"[\\/\0<>:\"|?*]+", "_", name)
	name = re.sub(r"\s+", " ", name).strip()
	return name[:180] or "file"


def _contract_folder_key(contract: str) -> str:
	contract = str(contract or "").strip()
	if not contract:
		return ""
	code = None
	try:
		if frappe.db.has_column("Contract", "contract_code"):
			code = frappe.db.get_value("Contract", contract, "contract_code")
	except Exception:
		code = None
	code = str(code or "").strip()
	return _safe_filename(code or contract)[:120] or _safe_filename(contract)[:120]


def _doc_type_folder_segments(*, doc_type: str, contract: str | None) -> list[str]:
	"""Return deterministic folder segments under 01_ДОКУМЕНТЫ for this doc type."""

	now = now_datetime()
	year = now.strftime("%Y")
	year_month = now.strftime("%Y-%m")

	if doc_type == DOC_TYPES[0]:  # Customer contracts
		contract_key = _contract_folder_key(contract or "") or "_NO_CONTRACT"
		return ["01_ДОГОВОРЫ_ЗАКАЗЧИК", contract_key]
	if doc_type == DOC_TYPES[1]:  # Contractors
		return ["02_ДОГОВОРЫ_ПОДРЯДЧИКИ"]
	if doc_type == DOC_TYPES[2]:  # Compliance
		return ["03_УДОСТОВЕРЕНИЯ_И_РАЗРЕШЕНИЯ"]
	if doc_type == DOC_TYPES[3]:  # Closing
		return ["04_ЗАКРЫВАЮЩИЕ_ДОКУМЕНТЫ", year, year_month]
	if doc_type == DOC_TYPES[4]:  # Incoming
		return ["05_КОРРЕСПОНДЕНЦИЯ", "01_ВХОДЯЩИЕ", year, year_month]
	if doc_type == DOC_TYPES[5]:  # Outgoing
		return ["05_КОРРЕСПОНДЕНЦИЯ", "02_ИСХОДЯЩИЕ", year, year_month]
	if len(DOC_TYPES) > 6 and doc_type == DOC_TYPES[6]:  # Internal docs
		return ["06_СЛУЖЕБНЫЕ_ДОКУМЕНТЫ", year, year_month]

	return ["99_НЕРАЗОБРАННОЕ"]


def _require_upload_access(*, user: str, project: str) -> None:
	if not project:
		frappe.throw(_("Missing project."))
	if user == "Administrator":
		return
	if not _has_any_role(user, UPLOAD_ROLES):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	if not user_has_project_access(user=user, project=project):
		frappe.throw(_("No access to project {0}.").format(project), frappe.PermissionError)


def _require_view_access(*, user: str, project: str) -> None:
	if not project:
		frappe.throw(_("Missing project."))
	if user == "Administrator":
		return
	if not user_has_project_access(user=user, project=project):
		frappe.throw(_("No access to project {0}.").format(project), frappe.PermissionError)


def _project_contract(project: str) -> str | None:
	meta = frappe.get_meta("Project")
	if not meta.has_field("contract"):
		return None
	try:
		val = frappe.db.get_value("Project", project, "contract")
	except Exception:
		val = None
	val = str(val or "").strip()
	return val or None


def _validate_contract_for_project(*, project: str, contract: str | None) -> str | None:
	contract = str(contract or "").strip()
	if not contract:
		return None
	if not frappe.db.exists("Contract", contract):
		frappe.throw(_("Contract not found: {0}.").format(contract))

	linked = _project_contract(project)
	if linked and linked != contract:
		frappe.throw(_("Contract {0} is not linked to Project {1}.").format(contract, project))
	return contract


def _ensure_project_docs_folder_id(*, service, project: str) -> str:
	# Ensure deterministic Drive structure exists (creates/updates Project.drive_folder_url + folders).
	ensure_drive_folders(project)

	meta = frappe.get_meta("Project")
	drive_url = None
	if meta.has_field("drive_folder_url") and frappe.db.has_column("Project", "drive_folder_url"):
		drive_url = frappe.db.get_value("Project", project, "drive_folder_url")
	drive_url = str(drive_url or "").strip() or None

	folder_id = _drive_folder_id_from_url(drive_url)
	if not folder_id:
		frappe.throw(_("Project Google Drive folder is not configured."))

	# Deterministic root for project documents (created by ensure_drive_folders as well).
	docs = ensure_folder(service, name="01_ДОКУМЕНТЫ", parent_id=folder_id)
	return docs.id


@frappe.whitelist(methods=["POST"])
def upload_project_document() -> dict:
	user = frappe.session.user
	project = str(frappe.form_dict.get("project") or "").strip()
	doc_title = str(frappe.form_dict.get("ferum_doc_title") or "").strip()
	doc_type = str(frappe.form_dict.get("ferum_doc_type") or "").strip()
	contract = str(frappe.form_dict.get("ferum_contract") or "").strip() or None

	_require_upload_access(user=user, project=project)

	if not frappe.db.exists("Project", project):
		frappe.throw(_("Project not found."))
	if not doc_title:
		frappe.throw(_("Missing document title."))
	if doc_type not in DOC_TYPES:
		frappe.throw(_("Invalid document type."))

	contract = _validate_contract_for_project(project=project, contract=contract)

	content = getattr(frappe.local, "uploaded_file", None)
	original_name = str(getattr(frappe.local, "uploaded_filename", "") or "").strip()
	if not content or not isinstance(content, (bytes, bytearray)):
		frappe.throw(_("Missing file."))
	if not original_name:
		original_name = "file"

	ext = Path(original_name).suffix
	drive_name = f"{_safe_filename(doc_title)}{ext}" if ext else _safe_filename(doc_title)

	service = get_drive_service()
	parent_id = _ensure_project_docs_folder_id(service=service, project=project)

	# Resolve deterministic folder path under 01_ДОКУМЕНТЫ
	folder_id = parent_id
	for segment in _doc_type_folder_segments(doc_type=doc_type, contract=contract):
		seg = _safe_filename(segment)[:120]
		folder_id = ensure_folder(service, name=seg, parent_id=folder_id).id

	tmp_path = None
	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix=ext or "") as tmp:
			tmp.write(content)
			tmp_path = tmp.name

		uploaded = upload_file(service, local_path=tmp_path, parent_id=folder_id, name=drive_name)
	finally:
		if tmp_path:
			try:
				os.unlink(tmp_path)
			except Exception:
				pass

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": original_name,
			"file_url": uploaded.web_view_link,
			"is_private": 0,
			"attached_to_doctype": "Project",
			"attached_to_name": project,
			"attached_to_field": ATTACHED_TO_FIELD,
			"ferum_doc_title": doc_title,
			"ferum_doc_type": doc_type,
			"ferum_contract": contract,
			"ferum_drive_file_id": uploaded.id,
		}
	)

	file_doc.insert(ignore_permissions=True)

	return {
		"ok": True,
		"file": file_doc.name,
		"file_url": file_doc.file_url,
		"file_name": file_doc.file_name,
		"project": project,
	}


@frappe.whitelist(methods=["POST"])
def upload_contract_document() -> dict:
	"""Upload a document from Contract context, but always attach to the linked Project."""

	contract = str(frappe.form_dict.get("contract") or frappe.form_dict.get("ferum_contract") or "").strip()
	if not contract:
		frappe.throw(_("Missing contract."))
	if not frappe.db.exists("Contract", contract):
		frappe.throw(_("Contract not found."))

	project = str(get_project_for_contract(contract) or "").strip()
	if not project:
		frappe.throw(_("Project for Contract is not found."))

	# Reuse the main implementation; it enforces permissions and validates contract linkage.
	frappe.form_dict["project"] = project
	frappe.form_dict["ferum_contract"] = contract
	return upload_project_document()


@frappe.whitelist()
@frappe.read_only()
def list_project_documents(
	project: str,
	*,
	doc_type: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
) -> list[dict]:
	user = frappe.session.user
	project = str(project or "").strip()
	doc_type = str(doc_type or "").strip() or None
	date_from = str(date_from or "").strip() or None
	date_to = str(date_to or "").strip() or None

	_require_view_access(user=user, project=project)

	filters: list[list] = [
		["File", "attached_to_doctype", "=", "Project"],
		["File", "attached_to_name", "=", project],
		["File", "attached_to_field", "=", ATTACHED_TO_FIELD],
	]

	if doc_type:
		filters.append(["File", "ferum_doc_type", "=", doc_type])
	if date_from:
		filters.append(["File", "creation", ">=", f"{date_from} 00:00:00"])
	if date_to:
		filters.append(["File", "creation", "<=", f"{date_to} 23:59:59"])

	if _is_client_user(user) and user != "Administrator" and not _has_any_role(user, {"System Manager"}):
		filters.append(["File", "ferum_doc_type", "in", sorted(CLIENT_ALLOWED_TYPES)])

	return frappe.get_all(
		"File",
		filters=filters,
		fields=[
			"name",
			"file_name",
			"file_url",
			"creation",
			"owner",
			"ferum_doc_title",
			"ferum_doc_type",
			"ferum_contract",
		],
		order_by="creation desc",
		limit=500,
	)


@frappe.whitelist()
@frappe.read_only()
def list_contract_documents(
	contract: str,
	*,
	doc_type: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
) -> list[dict]:
	user = frappe.session.user
	contract = str(contract or "").strip()
	doc_type = str(doc_type or "").strip() or None
	date_from = str(date_from or "").strip() or None
	date_to = str(date_to or "").strip() or None

	if not contract:
		frappe.throw(_("Missing contract."))
	if not frappe.db.exists("Contract", contract):
		frappe.throw(_("Contract not found."))

	meta = frappe.get_meta("Project")
	projects_by_contract: list[str] = []
	if meta.has_field("contract"):
		projects_by_contract = frappe.get_all(
			"Project",
			filters={"contract": contract},
			pluck="name",
			limit=500,
		)

	allowed_projects = []
	for p in projects_by_contract:
		if user == "Administrator" or user_has_project_access(user=user, project=p):
			allowed_projects.append(p)

	filters: list[list] = [
		["File", "attached_to_doctype", "=", "Project"],
		["File", "attached_to_field", "=", ATTACHED_TO_FIELD],
	]

	if doc_type:
		filters.append(["File", "ferum_doc_type", "=", doc_type])
	if date_from:
		filters.append(["File", "creation", ">=", f"{date_from} 00:00:00"])
	if date_to:
		filters.append(["File", "creation", "<=", f"{date_to} 23:59:59"])

	or_filters: list[list] = [["File", "ferum_contract", "=", contract]]
	if allowed_projects:
		or_filters.append(["File", "attached_to_name", "in", allowed_projects])

	if _is_client_user(user) and user != "Administrator" and not _has_any_role(user, {"System Manager"}):
		filters.append(["File", "ferum_doc_type", "in", sorted(CLIENT_ALLOWED_TYPES)])

	rows = frappe.get_all(
		"File",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"file_name",
			"file_url",
			"creation",
			"owner",
			"ferum_doc_title",
			"ferum_doc_type",
			"attached_to_name",
		],
		order_by="creation desc",
		limit=500,
	)

	out: list[dict] = []
	for r in rows:
		project = str(r.get("attached_to_name") or "").strip()
		if not project:
			continue
		if user != "Administrator" and not user_has_project_access(user=user, project=project):
			continue
		r["project"] = project
		out.append(r)
	return out
