from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.desk.query_report import (
	get_prepared_report_result,
	generate_report_result,
	get_report_doc,
	validate_filters_permissions,
)
from frappe.monitor import add_data_to_monitor
from frappe.utils import sbool


def _parse_filters(filters):
	if not filters:
		return {}

	if isinstance(filters, str):
		try:
			return json.loads(filters)
		except Exception:
			return {}

	return filters


def _ensure_named_placeholders(filters, report):
	"""Make Query Reports tolerant to empty filter dicts.

	Frappe's Query Report UI sends only non-empty filters.
	If a query uses `%(field)s` placeholders and the filter is empty, MySQL execution fails with KeyError.

	We pre-fill missing placeholder keys with configured defaults (or empty string) so optional filters work.
	"""

	if not isinstance(filters, dict):
		return filters

	query = getattr(report, "query", None) or ""
	placeholders = set(re.findall(r"%\(([^)]+)\)s", query))
	if not placeholders:
		return filters

	defaults = {}
	for df in report.get("filters") or []:
		fieldname = getattr(df, "fieldname", None)
		if not fieldname:
			continue
		defaults[fieldname] = getattr(df, "default", None)

	for key in placeholders:
		if key not in filters:
			default = defaults.get(key)
			filters[key] = default if default is not None else ""

	return filters


@frappe.whitelist()
@frappe.read_only()
def run(
	report_name,
	filters=None,
	user=None,
	ignore_prepared_report=False,
	custom_columns=None,
	is_tree=False,
	parent_field=None,
	are_default_filters=True,
):
	# Same signature as core `frappe.desk.query_report.run`, but ensures named placeholders are present.
	if not user:
		user = frappe.session.user

	validate_filters_permissions(report_name, filters, user)
	report = get_report_doc(report_name)

	if not frappe.has_permission(report.ref_doctype, "report"):
		frappe.msgprint(
			_("Must have report permission to access this report."),
			raise_exception=True,
		)

	# Match core behavior for custom reports / default filters
	if sbool(are_default_filters) and report.get("custom_filters"):
		filters = report.custom_filters

	filters = _parse_filters(filters)
	filters = _ensure_named_placeholders(filters, report)

	result = None
	try:
		if report.prepared_report and not sbool(ignore_prepared_report) and not custom_columns:
			dn = ""
			if filters and isinstance(filters, dict):
				dn = filters.pop("prepared_report_name", None) or ""
			result = get_prepared_report_result(report, filters, dn, user)
		else:
			result = generate_report_result(report, filters, user, custom_columns, is_tree, parent_field)
			add_data_to_monitor(report=report.reference_report or report.name)
	except Exception:
		frappe.log_error("Report Error")
		raise

	result["add_total_row"] = report.add_total_row and not result.get("skip_total_row", False)

	# Match core behavior for custom filters
	if sbool(are_default_filters) and report.get("custom_filters"):
		result["custom_filters"] = report.custom_filters

	return result
