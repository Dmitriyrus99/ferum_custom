from __future__ import annotations

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def _upsert_property_setter(
	*,
	doctype: str,
	fieldname: str,
	prop: str,
	value: str | int,
	prop_type: str,
) -> None:
	existing = frappe.db.get_value(
		"Property Setter",
		{"doc_type": doctype, "field_name": fieldname, "property": prop},
		"name",
	)
	if existing:
		frappe.db.set_value(
			"Property Setter",
			existing,
			{"value": str(value), "property_type": prop_type},
			update_modified=False,
		)
		return

	make_property_setter(
		doctype,
		fieldname,
		prop,
		value,
		prop_type,
		for_doctype=False,
		validate_fields_for_doctype=False,
		is_system_generated=False,
	)


def execute() -> None:
	"""Hide ERPNext Project fields not used in Ferum P0 workflow."""
	if not frappe.db.exists("DocType", "Project"):
		return

	meta = frappe.get_meta("Project")

	to_hide = [
		# Progress tracking (timesheets / progress collection)
		"percent_complete_method",
		"percent_complete",
		"collect_progress",
		"holiday_list",
		"frequency",
		"from_time",
		"to_time",
		"first_email",
		"second_email",
		"daily_time_to_send",
		"day_to_send",
		"weekly_time_to_send",
		"subject",
		"message",
		# Timesheet-derived fields
		"actual_start_date",
		"actual_time",
		"actual_end_date",
		# Costing/finance aggregates
		"estimated_costing",
		"total_costing_amount",
		"total_purchase_cost",
		"total_sales_amount",
		"total_billable_amount",
		"total_billed_amount",
		"total_consumed_material_cost",
		"cost_center",
		"gross_margin",
		"per_gross_margin",
		# Sales/order linkage (not used in P0)
		"sales_order",
		"project_template",
	]

	for fieldname in to_hide:
		if not meta.has_field(fieldname):
			continue
		_upsert_property_setter(
			doctype="Project",
			fieldname=fieldname,
			prop="hidden",
			value=1,
			prop_type="Check",
		)

	frappe.clear_cache()

