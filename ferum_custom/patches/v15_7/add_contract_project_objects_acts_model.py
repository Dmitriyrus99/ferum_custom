from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def _create_custom_fields() -> None:
	create_custom_fields(
		{
			"Contract": [
				{
					"fieldname": "company",
					"label": "Company",
					"fieldtype": "Link",
					"options": "Company",
					"insert_after": "party_name",
					"reqd": 1,
				},
				{
					"fieldname": "document_mode",
					"label": "Document Mode",
					"fieldtype": "Select",
					"options": "UPD_ONLY\nACT_PLUS_INVOICE",
					"insert_after": "company",
					"reqd": 1,
				},
				{
					"fieldname": "submission_channel",
					"label": "Submission Channel",
					"fieldtype": "Select",
					"options": "EIS\nPIK\nMAIL\nEDO\nOTHER",
					"insert_after": "document_mode",
					"reqd": 1,
				},
				{
					"fieldname": "acts_deadline_day",
					"label": "Acts Deadline Day",
					"fieldtype": "Int",
					"insert_after": "submission_channel",
				},
				{
					"fieldname": "payment_terms_template",
					"label": "Payment Terms Template",
					"fieldtype": "Link",
					"options": "Payment Terms Template",
					"insert_after": "acts_deadline_day",
				},
				{
					"fieldname": "project_manager",
					"label": "Project Manager",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "payment_terms_template",
				},
				{
					"fieldname": "account_manager",
					"label": "Account Manager",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "project_manager",
				},
				{
					"fieldname": "is_portal_visible",
					"label": "Portal Visible",
					"fieldtype": "Check",
					"default": 1,
					"insert_after": "account_manager",
				},
				{
					"fieldname": "contract_code",
					"label": "Contract Code",
					"fieldtype": "Data",
					"insert_after": "is_portal_visible",
				},
				{
					"fieldname": "contract_value",
					"label": "Contract Value",
					"fieldtype": "Currency",
					"insert_after": "contract_code",
				},
				{
					"fieldname": "document_folder_url",
					"label": "Document Folder URL",
					"fieldtype": "Data",
					"insert_after": "contract_value",
				},
			],
			"Project": [
				{
					"fieldname": "contract",
					"label": "Contract",
					"fieldtype": "Link",
					"options": "Contract",
					"insert_after": "customer",
				}
			],
		},
		ignore_validate=True,
	)


def _create_property_setters() -> None:
	# Contract naming series (autoname)
	if frappe.db.exists("DocType", "Contract"):
		make_property_setter(
			"Contract",
			None,
			"autoname",
			"CT-.YYYY.-.#####",
			"Data",
		)

	# Add new series to Project naming_series field options
	if frappe.db.exists("DocType", "Project"):
		current_options = frappe.db.get_value(
			"DocField",
			{"parent": "Project", "parenttype": "DocType", "fieldname": "naming_series"},
			"options",
		)
		if current_options and "PRJ-.YYYY.-.#####" not in current_options:
			new_options = f"{current_options}\nPRJ-.YYYY.-.#####"
			make_property_setter("Project", "naming_series", "options", new_options, "Text")


def execute() -> None:
	_create_custom_fields()
	_create_property_setters()
	frappe.clear_cache()
