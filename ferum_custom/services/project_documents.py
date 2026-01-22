from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from ferum_custom.services.project_documents_config import ATTACHED_TO_FIELD, DOC_TYPES


def _is_ferum_project_document(doc: Document) -> bool:
	attached_to_doctype = str(getattr(doc, "attached_to_doctype", "") or "").strip()
	attached_to_field = str(getattr(doc, "attached_to_field", "") or "").strip()
	return attached_to_doctype == "Project" and attached_to_field == ATTACHED_TO_FIELD


def validate_project_document_file(doc: Document, method: str | None = None) -> None:
	"""Validate Ferum Project documents stored in File (server-side enforcement).

	This runs on File.validate but only applies to records created by the Ferum "Project Documents" feature,
	identified by `attached_to_doctype=Project` and `attached_to_field=ferum_project_documents`.
	"""

	if not _is_ferum_project_document(doc):
		return

	project = str(getattr(doc, "attached_to_name", "") or "").strip()
	if not project:
		frappe.throw(_("Missing project."), frappe.ValidationError)
	if not frappe.db.exists("Project", project):
		frappe.throw(_("Project not found."), frappe.ValidationError)

	title = str(getattr(doc, "ferum_doc_title", "") or "").strip()
	if not title:
		frappe.throw(_("Missing document title."), frappe.ValidationError)

	doc_type = str(getattr(doc, "ferum_doc_type", "") or "").strip()
	if doc_type not in DOC_TYPES:
		frappe.throw(_("Invalid document type."), frappe.ValidationError)

	file_url = str(getattr(doc, "file_url", "") or "").strip()
	if not file_url:
		frappe.throw(_("Missing file URL."), frappe.ValidationError)

	drive_id = str(getattr(doc, "ferum_drive_file_id", "") or "").strip()
	if not drive_id:
		frappe.throw(_("Missing Google Drive file id."), frappe.ValidationError)

	contract = str(getattr(doc, "ferum_contract", "") or "").strip()
	if not contract:
		return

	if not frappe.db.exists("Contract", contract):
		frappe.throw(_("Contract not found: {0}.").format(contract), frappe.ValidationError)

	project_meta = frappe.get_meta("Project")
	if project_meta.has_field("contract") and frappe.db.has_column("Project", "contract"):
		linked = frappe.db.get_value("Project", project, "contract")
		linked = str(linked or "").strip()
		if linked and linked != contract:
			frappe.throw(
				_("Contract {0} is not linked to Project {1}.").format(contract, project),
				frappe.ValidationError,
			)

