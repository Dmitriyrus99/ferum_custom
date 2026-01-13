from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, nowdate
from frappe.utils.data import escape_html

from ferum_custom.utils.role_resolution import (
	FERUM_DIRECTOR_ROLES,
	FERUM_OFFICE_MANAGER_ROLES,
	FERUM_TENDER_SPECIALIST_ROLES,
	first_enabled_user_with_roles,
)


STAGES: list[str] = [
	"Tender Won",
	"Contact Established",
	"Contract Signed",
	"Contractor Selected/Contracted",
	"Initial Document Package Sent",
	"Primary Survey Completed",
	"Act & Defects Sent",
	"Invoice/Act Sent",
	"Customer Received Docs Confirmed",
	"Payment Received",
]


def _stage_index(stage: str | None) -> int:
	try:
		return STAGES.index(stage or "")
	except ValueError:
		return 0


def _at_least(stage: str | None, threshold: str) -> bool:
	return _stage_index(stage) >= _stage_index(threshold)


@dataclass(frozen=True)
class GateError:
	title: str
	details: str


def _require(condition: bool, title: str, details: str, errors: list[GateError]) -> None:
	if condition:
		return
	errors.append(GateError(title=title, details=details))


def _has_verified_official_email(customer_contacts: list[dict]) -> bool:
	for row in customer_contacts:
		if int(row.get("official_email_verified") or 0) == 1 and (row.get("official_email") or "").strip():
			return True
	return False


def _all_required_checklist_done(checklist: list[dict]) -> bool:
	required_rows = [r for r in checklist if int(r.get("required") or 0) == 1]
	if not required_rows:
		return False
	return all(int(r.get("done") or 0) == 1 for r in required_rows)


def _has_valid_outbound_mail_item(items: list[dict]) -> bool:
	# Minimal invariants: tracking + at least one scan.
	for row in items:
		tracking = (row.get("russian_post_tracking") or "").strip()
		inventory_scan = (row.get("inventory_scan") or "").strip()
		receipt_scan = (row.get("receipt_scan") or "").strip()
		if tracking and (inventory_scan or receipt_scan):
			return True
	return False


def apply_project_p0_defaults(doc: Document, method: str | None = None) -> None:
	"""Best-effort defaults for P0 deadlines.

	These defaults are intentionally conservative and can be overridden by users.
	"""
	_unused_method = method
	if not getattr(doc, "ferum_stage", None):
		return

	contract_signed = getattr(doc, "contract_signed_date", None)
	if contract_signed and not getattr(doc, "start_work_date", None):
		doc.start_work_date = contract_signed

	start_work_date = getattr(doc, "start_work_date", None)
	if start_work_date and not getattr(doc, "photo_survey_deadline", None):
		doc.photo_survey_deadline = add_days(start_work_date, 15)

	if start_work_date and not getattr(doc, "initial_survey_act_due", None):
		doc.initial_survey_act_due = add_days(start_work_date, 20)

	if contract_signed and not getattr(doc, "contractor_selected_deadline", None):
		doc.contractor_selected_deadline = add_days(contract_signed, 10)


def validate_project_p0_stage_gates(doc: Document, method: str | None = None) -> None:
	_unused_method = method
	if not getattr(doc, "ferum_stage", None):
		return
	if int(getattr(doc, "ferum_p0_enabled", 0) or 0) != 1:
		return

	apply_project_p0_defaults(doc)
	auto_advance_project_stage(doc)
	_apply_outbound_mail_defaults(doc)

	errors: list[GateError] = []
	stage = getattr(doc, "ferum_stage", None)

	# Base fields for Tender Won (P0 required tender block).
	_require(bool((getattr(doc, "eis_etp_url", None) or "").strip()), "Tender", "EIS/ETP URL is required.", errors)
	_require(
		bool((getattr(doc, "tender_customer_name", None) or "").strip()),
		"Tender",
		"Tender customer name is required.",
		errors,
	)
	_require(bool(getattr(doc, "tender_price", None)), "Tender", "Tender price is required.", errors)
	_require(bool(getattr(doc, "tender_protocol_date", None)), "Tender", "Tender protocol date is required.", errors)
	_require(bool(getattr(doc, "tender_term_start", None)), "Tender", "Tender term start is required.", errors)
	_require(bool(getattr(doc, "tender_term_end", None)), "Tender", "Tender term end is required.", errors)

	if _at_least(stage, "Contact Established"):
		contacts = list(doc.get("customer_contacts") or [])
		_require(bool(contacts), "Customer Contacts", "At least one customer contact is required.", errors)
		_require(
			_has_verified_official_email(contacts),
			"Customer Contacts",
			"At least one official email must be verified by contract/EIS.",
			errors,
		)
		_require(
			bool(getattr(doc, "welcome_email_sent_date", None)),
			"Welcome Email",
			"Welcome email sent date must be set.",
			errors,
		)

	if _at_least(stage, "Contract Signed"):
		_require(
			bool(getattr(doc, "contract_signed_date", None)),
			"Contract",
			"Contract signed date is required.",
			errors,
		)
		legal_status = (getattr(doc, "legal_review_status", None) or "").strip()
		override = int(getattr(doc, "legal_review_director_override", 0) or 0) == 1
		_require(
			legal_status == "Approved" or override,
			"Legal Review",
			"Legal review must be Approved (or director override).",
			errors,
		)

	if _at_least(stage, "Contractor Selected/Contracted"):
		sub_allowed = (getattr(doc, "subcontracting_allowed", None) or "Unknown").strip()
		_require(sub_allowed != "Unknown", "Contractor", "Subcontracting allowed must not be Unknown.", errors)

		exec_mode = (getattr(doc, "execution_mode", None) or "").strip()
		if sub_allowed == "Forbidden":
			_require(
				exec_mode in {"In-house", "Self-employed", "GPH"},
				"Contractor",
				"Execution mode must be In-house/Self-employed/GPH when subcontracting is forbidden.",
				errors,
			)
			_require(
				int(getattr(doc, "director_approved_execution_mode", 0) or 0) == 1,
				"Contractor",
				"Director must approve execution scenario when subcontracting is forbidden.",
				errors,
			)
		if sub_allowed == "Allowed" and int(getattr(doc, "subcontractor_selected", 0) or 0) == 1:
			_require(
				int(getattr(doc, "director_approved_subcontractor", 0) or 0) == 1,
				"Contractor",
				"Director approval for subcontractor is required.",
				errors,
			)
			_require(
				int(getattr(doc, "subcontractor_contract_signed", 0) or 0) == 1,
				"Contractor",
				"Subcontractor contract must be marked as signed.",
				errors,
			)
			_require(
				bool((getattr(doc, "subcontractor_contract_file", None) or "").strip()),
				"Contractor",
				"Subcontractor contract file must be attached.",
				errors,
			)

	if _at_least(stage, "Initial Document Package Sent"):
		items = list(doc.get("outbound_mail_items") or [])
		_require(
			_has_valid_outbound_mail_item(items),
			"Outbound Mail",
			"At least one outbound mail item must have tracking and scans.",
			errors,
		)

	if _at_least(stage, "Primary Survey Completed"):
		_require(bool((getattr(doc, "drive_folder_url", None) or "").strip()), "Survey", "Drive folder URL is required.", errors)
		photo_format = (getattr(doc, "photo_survey_format", None) or "").strip()
		if photo_format == "Photo-only":
			_require(
				int(getattr(doc, "photo_only_confirmed", 0) or 0) == 1,
				"Survey",
				"Photo-only format must be confirmed by PM.",
				errors,
			)
		else:
			checklist = list(doc.get("survey_checklist") or [])
			_require(
				_all_required_checklist_done(checklist),
				"Survey",
				"All required checklist items must be marked as done.",
				errors,
			)

	if _at_least(stage, "Act & Defects Sent"):
		_require(
			bool((getattr(doc, "initial_survey_act_file", None) or "").strip()),
			"Survey Act",
			"Initial survey act file is required.",
			errors,
		)
		_require(
			bool((getattr(doc, "defects_list_file", None) or "").strip()),
			"Survey Act",
			"Defects list file is required.",
			errors,
		)
		if int(getattr(doc, "director_approval_required", 0) or 0) == 1:
			_require(
				int(getattr(doc, "director_approved", 0) or 0) == 1,
				"Survey Act",
				"Director approval is required.",
				errors,
			)
		_require(
			bool(getattr(doc, "sent_to_customer_date", None)),
			"Survey Act",
			"Sent to customer date is required.",
			errors,
		)

	if _at_least(stage, "Invoice/Act Sent"):
		periods = list(doc.get("billing_periods") or [])
		_require(bool(periods), "Billing", "At least one billing period must exist.", errors)

	if _at_least(stage, "Customer Received Docs Confirmed"):
		_require(
			int(getattr(doc, "customer_received_docs_confirmed", 0) or 0) == 1,
			"Billing",
			"Customer received docs must be confirmed.",
			errors,
		)

	if _at_least(stage, "Payment Received"):
		_require(
			(getattr(doc, "payment_status", None) or "").strip() == "Paid",
			"Payment",
			"Payment status must be Paid.",
			errors,
		)

	if errors:
		msg = "<br>".join([f"<b>{frappe.bold(e.title)}</b>: {escape_html(e.details)}" for e in errors])
		frappe.throw(_(msg))


def auto_advance_project_stage(doc: Document, method: str | None = None) -> None:
	"""Auto-advance stage for mechanical transitions (P0).

	Currently:
	- If outbound mail evidence exists -> set stage at least to 'Initial Document Package Sent'
	"""
	_unused_method = method
	if not getattr(doc, "ferum_stage", None):
		return

	items = list(doc.get("outbound_mail_items") or [])
	current_stage = getattr(doc, "ferum_stage", None)
	# Do not skip earlier gates: only advance from the immediately previous stage group.
	if (
		_has_valid_outbound_mail_item(items)
		and _at_least(current_stage, "Contractor Selected/Contracted")
		and not _at_least(current_stage, "Initial Document Package Sent")
	):
		doc.ferum_stage = "Initial Document Package Sent"
		# Comment is added after save by on_update handler (to avoid side-effects in validate).


def _apply_outbound_mail_defaults(doc: Document) -> None:
	"""Fill sent_by for outbound mail rows (Office Manager requirement)."""
	for row in doc.get("outbound_mail_items") or []:
		if getattr(row, "sent_date", None) and not getattr(row, "sent_by", None):
			row.sent_by = frappe.session.user


def maybe_trigger_customer_ignored_mail_task(doc: Document) -> None:
	"""If customer ignores act/defects, create a ToDo for office manager (P0 minimal)."""
	if not getattr(doc, "ferum_stage", None):
		return
	if not _at_least(getattr(doc, "ferum_stage", None), "Act & Defects Sent"):
		return
	if int(getattr(doc, "if_customer_ignored_trigger_mail_task", 0) or 0) == 1:
		return
	sent_date = getattr(doc, "sent_to_customer_date", None)
	if not sent_date:
		return

	# Minimal rule: 7 days after sent_to_customer_date.
	if nowdate() <= add_days(sent_date, 7):
		return

	assignee = first_enabled_user_with_roles(FERUM_OFFICE_MANAGER_ROLES) or "Administrator"
	_create_todo(
		assignee=assignee,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		description=f"Customer ignored Act/Defects. Prepare registered mail package for Project {doc.name}.",
	)
	doc.if_customer_ignored_trigger_mail_task = 1


def create_initial_project_todos(doc: Document, method: str | None = None) -> None:
	_unused_method = method
	if not getattr(doc, "ferum_stage", None):
		return
	if int(getattr(doc, "ferum_p0_enabled", 0) or 0) != 1:
		return

	pm = (getattr(doc, "project_manager", None) or "").strip()
	director = first_enabled_user_with_roles(FERUM_DIRECTOR_ROLES) or "Administrator"
	tender_specialist = first_enabled_user_with_roles(FERUM_TENDER_SPECIALIST_ROLES) or "Administrator"

	if pm:
		_create_todo(
			assignee=pm,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			description="Ознакомиться с проектом договора/ТЗ (Tender Won).",
		)
		_create_todo(
			assignee=pm,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			description="Запросить контакты заказчика (официальный email из договора/ЭТП).",
		)

	_create_todo(
		assignee=tender_specialist,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		description="Передать проект контракта юристу на проверку (зафиксировать статус legal_review_status).",
	)

	_create_todo(
		assignee=director,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		description="Новый проект воронки (Tender Won): контроль и назначение приоритетов.",
	)


def _create_todo(*, assignee: str, reference_doctype: str, reference_name: str, description: str) -> None:
	try:
		todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": assignee,
				"reference_type": reference_doctype,
				"reference_name": reference_name,
				"description": description,
			}
		)
		todo.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Project P0: failed to create ToDo")
