from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _project_sites_child_doctype() -> str:
	"""Return the legacy child doctype used by Project.project_sites (Table)."""
	if frappe.db.exists("DocType", "Project Site Row"):
		return "Project Site Row"
	try:
		dt = frappe.get_doc("DocType", "Project Site")
		if int(getattr(dt, "istable", 0) or 0) == 1:
			return "Project Site"
	except Exception:
		pass
	return "Project Site Row"


def _field_exists(doctype: str, fieldname: str) -> bool:
	return bool(
		frappe.db.get_value(
			"Custom Field",
			{"dt": doctype, "fieldname": fieldname},
			"name",
		)
	) or bool(
		frappe.db.get_value(
			"DocField",
			{"parent": doctype, "parenttype": "DocType", "fieldname": fieldname},
			"name",
		)
	)


def _create_project_fields() -> None:
	# We use a dedicated stage field to avoid breaking ERPNext's native Project.status semantics.
	stage_options = "\n".join(
		[
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
	)

	custom_fields: list[dict] = [
		{
			"fieldname": "ferum_stage",
			"label": "Ferum Stage",
			"fieldtype": "Select",
			"options": stage_options,
			"default": "Tender Won",
			"insert_after": "status",
			"reqd": 1,
		},
		{
			"fieldname": "ferum_p0_tab",
			"label": "Ferum P0",
			"fieldtype": "Tab Break",
			"insert_after": "ferum_stage",
		},
		{
			"fieldname": "tender_section",
			"label": "Tender",
			"fieldtype": "Section Break",
			"insert_after": "ferum_p0_tab",
		},
		{
			"fieldname": "tender_source",
			"label": "Tender Source",
			"fieldtype": "Data",
			"insert_after": "tender_section",
		},
		{
			"fieldname": "eis_etp_url",
			"label": "EIS/ETP URL",
			"fieldtype": "Data",
			"insert_after": "tender_source",
		},
		{
			"fieldname": "tender_customer_name",
			"label": "Tender Customer Name",
			"fieldtype": "Data",
			"insert_after": "eis_etp_url",
		},
		{
			"fieldname": "tender_price",
			"label": "Tender Price",
			"fieldtype": "Currency",
			"insert_after": "tender_customer_name",
		},
		{
			"fieldname": "tender_term_start",
			"label": "Tender Term Start",
			"fieldtype": "Date",
			"insert_after": "tender_price",
		},
		{
			"fieldname": "tender_term_end",
			"label": "Tender Term End",
			"fieldtype": "Date",
			"insert_after": "tender_term_start",
		},
		{
			"fieldname": "tender_protocol_date",
			"label": "Tender Protocol Date",
			"fieldtype": "Date",
			"insert_after": "tender_term_end",
		},
		{
			"fieldname": "contacts_section",
			"label": "Customer Contacts",
			"fieldtype": "Section Break",
			"insert_after": "tender_protocol_date",
		},
		{
			"fieldname": "customer_contacts",
			"label": "Customer Contacts",
			"fieldtype": "Table",
			"options": "Project Customer Contact",
			"insert_after": "contacts_section",
		},
		{
			"fieldname": "project_sites_section",
			"label": "Project Sites",
			"fieldtype": "Section Break",
			"insert_after": "customer_contacts",
		},
		{
			"fieldname": "project_sites",
			"label": "Project Sites",
			"fieldtype": "Table",
			"options": _project_sites_child_doctype(),
			"insert_after": "project_sites_section",
		},
		{
			"fieldname": "contract_review_section",
			"label": "Contract Review (Before Signing)",
			"fieldtype": "Section Break",
			"insert_after": "project_sites",
		},
		{
			"fieldname": "contract_draft_reviewed",
			"label": "Contract Draft Reviewed",
			"fieldtype": "Check",
			"insert_after": "contract_review_section",
		},
		{
			"fieldname": "subcontracting_allowed",
			"label": "Subcontracting Allowed",
			"fieldtype": "Select",
			"options": "Allowed\nForbidden\nUnknown",
			"default": "Unknown",
			"insert_after": "contract_draft_reviewed",
		},
		{
			"fieldname": "legal_review_required",
			"label": "Legal Review Required",
			"fieldtype": "Check",
			"insert_after": "subcontracting_allowed",
		},
		{
			"fieldname": "legal_review_status",
			"label": "Legal Review Status",
			"fieldtype": "Select",
			"options": "Draft\nSent\nApproved\nReturned",
			"default": "Draft",
			"insert_after": "legal_review_required",
		},
		{
			"fieldname": "contract_signed_date",
			"label": "Contract Signed Date",
			"fieldtype": "Date",
			"insert_after": "legal_review_status",
		},
		{
			"fieldname": "contractor_section",
			"label": "Contractor",
			"fieldtype": "Section Break",
			"insert_after": "contract_signed_date",
		},
		{
			"fieldname": "execution_mode",
			"label": "Execution Mode",
			"fieldtype": "Select",
			"options": "In-house\nSelf-employed\nGPH\nSubcontractor",
			"insert_after": "contractor_section",
		},
		{
			"fieldname": "subcontractor_selected",
			"label": "Subcontractor Selected",
			"fieldtype": "Check",
			"insert_after": "execution_mode",
		},
		{
			"fieldname": "subcontractor_party",
			"label": "Subcontractor Party",
			"fieldtype": "Link",
			"options": "Supplier",
			"insert_after": "subcontractor_selected",
		},
		{
			"fieldname": "subcontractor_contact_phone",
			"label": "Subcontractor Contact Phone",
			"fieldtype": "Data",
			"insert_after": "subcontractor_party",
		},
		{
			"fieldname": "subcontractor_contract_signed",
			"label": "Subcontractor Contract Signed",
			"fieldtype": "Check",
			"insert_after": "subcontractor_contact_phone",
		},
		{
			"fieldname": "subcontractor_contract_file",
			"label": "Subcontractor Contract File",
			"fieldtype": "Attach",
			"insert_after": "subcontractor_contract_signed",
		},
		{
			"fieldname": "director_approved_subcontractor",
			"label": "Director Approved Subcontractor",
			"fieldtype": "Check",
			"insert_after": "subcontractor_contract_file",
		},
		{
			"fieldname": "mail_section",
			"label": "Outbound Mail (Russian Post)",
			"fieldtype": "Section Break",
			"insert_after": "director_approved_subcontractor",
		},
		{
			"fieldname": "outbound_mail_items",
			"label": "Outbound Mail Items",
			"fieldtype": "Table",
			"options": "Project Outbound Mail Item",
			"insert_after": "mail_section",
		},
		{
			"fieldname": "welcome_email_sent_date",
			"label": "Welcome Email Sent Date",
			"fieldtype": "Date",
			"insert_after": "outbound_mail_items",
		},
		{
			"fieldname": "survey_section",
			"label": "Primary Survey",
			"fieldtype": "Section Break",
			"insert_after": "welcome_email_sent_date",
		},
		{
			"fieldname": "start_work_date",
			"label": "Start Work Date",
			"fieldtype": "Date",
			"insert_after": "survey_section",
		},
		{
			"fieldname": "photo_survey_deadline",
			"label": "Photo Survey Deadline",
			"fieldtype": "Date",
			"insert_after": "start_work_date",
		},
		{
			"fieldname": "photo_survey_format",
			"label": "Photo Survey Format",
			"fieldtype": "Select",
			"options": "Checklist+Photo\nPhoto-only",
			"insert_after": "photo_survey_deadline",
		},
		{
			"fieldname": "drive_folder_url",
			"label": "Drive Folder URL",
			"fieldtype": "Data",
			"insert_after": "photo_survey_format",
		},
		{
			"fieldname": "survey_checklist",
			"label": "Survey Checklist",
			"fieldtype": "Table",
			"options": "Project Survey Checklist Item",
			"insert_after": "drive_folder_url",
		},
		{
			"fieldname": "survey_docs_section",
			"label": "Survey Act & Defects",
			"fieldtype": "Section Break",
			"insert_after": "survey_checklist",
		},
		{
			"fieldname": "initial_survey_act_due",
			"label": "Initial Survey Act Due",
			"fieldtype": "Date",
			"insert_after": "survey_docs_section",
		},
		{
			"fieldname": "initial_survey_act_file",
			"label": "Initial Survey Act File",
			"fieldtype": "Attach",
			"insert_after": "initial_survey_act_due",
		},
		{
			"fieldname": "defects_list_file",
			"label": "Defects List File",
			"fieldtype": "Attach",
			"insert_after": "initial_survey_act_file",
		},
		{
			"fieldname": "director_approval_required",
			"label": "Director Approval Required",
			"fieldtype": "Check",
			"default": 1,
			"insert_after": "defects_list_file",
		},
		{
			"fieldname": "director_approved",
			"label": "Director Approved",
			"fieldtype": "Check",
			"insert_after": "director_approval_required",
		},
		{
			"fieldname": "sent_to_customer_date",
			"label": "Sent To Customer Date",
			"fieldtype": "Date",
			"insert_after": "director_approved",
		},
		{
			"fieldname": "if_customer_ignored_trigger_mail_task",
			"label": "Customer Ignored → Trigger Mail Task",
			"fieldtype": "Check",
			"insert_after": "sent_to_customer_date",
		},
		{
			"fieldname": "billing_section",
			"label": "Billing Periods",
			"fieldtype": "Section Break",
			"insert_after": "if_customer_ignored_trigger_mail_task",
		},
		{
			"fieldname": "billing_periods",
			"label": "Billing Periods",
			"fieldtype": "Table",
			"options": "Project Billing Period",
			"insert_after": "billing_section",
		},
		{
			"fieldname": "customer_received_docs_confirmed",
			"label": "Customer Received Docs Confirmed",
			"fieldtype": "Check",
			"insert_after": "billing_periods",
		},
		{
			"fieldname": "payment_received_date",
			"label": "Payment Received Date",
			"fieldtype": "Date",
			"insert_after": "customer_received_docs_confirmed",
		},
		{
			"fieldname": "payment_status",
			"label": "Payment Status",
			"fieldtype": "Select",
			"options": "Unpaid\nPartly\nPaid",
			"default": "Unpaid",
			"insert_after": "payment_received_date",
		},
		{
			"fieldname": "payment_control_notes",
			"label": "Payment Control Notes",
			"fieldtype": "Small Text",
			"insert_after": "payment_status",
		},
		{
			"fieldname": "contractor_payments_section",
			"label": "Contractor Payments (Minimal)",
			"fieldtype": "Section Break",
			"insert_after": "payment_control_notes",
		},
		{
			"fieldname": "contractor_payment_due_rule",
			"label": "Contractor Payment Due Rule",
			"fieldtype": "Data",
			"insert_after": "contractor_payments_section",
		},
		{
			"fieldname": "contractor_docs_received",
			"label": "Contractor Docs Received",
			"fieldtype": "Check",
			"insert_after": "contractor_payment_due_rule",
		},
		{
			"fieldname": "contractor_originals_received",
			"label": "Contractor Originals Received",
			"fieldtype": "Check",
			"insert_after": "contractor_docs_received",
		},
		{
			"fieldname": "contractor_payment_request_link",
			"label": "Contractor Payment Request Link",
			"fieldtype": "Data",
			"insert_after": "contractor_originals_received",
		},
		{
			"fieldname": "deadlines_section",
			"label": "Deadlines",
			"fieldtype": "Section Break",
			"insert_after": "contractor_payment_request_link",
		},
		{
			"fieldname": "contractor_selected_deadline",
			"label": "Contractor Selected Deadline",
			"fieldtype": "Date",
			"insert_after": "deadlines_section",
		},
	]

	create_custom_fields({"Project": custom_fields}, ignore_validate=True)


def execute() -> None:
	if not frappe.db.exists("DocType", "Project"):
		return

	# Child table doctypes must exist.
	required_table_dts = [
		"Project Customer Contact",
		"Project Outbound Mail Item",
		"Project Survey Checklist Item",
		"Project Billing Period",
		_project_sites_child_doctype(),
	]
	for dt in required_table_dts:
		if not frappe.db.exists("DocType", dt):
			# Doctype files are part of the app, but migration order matters.
			return

	# Idempotency: if stage field exists, assume patch already applied.
	if _field_exists("Project", "ferum_stage"):
		return

	_create_project_fields()
	frappe.clear_cache()
