from __future__ import annotations

import frappe


def execute() -> None:
	"""Soft-rollout P0 gates: disable for Projects missing tender base fields.

	Reason: existing Projects may predate P0 and would become uneditable due to strict stage gates.
	Users can enable P0 per-project once the tender block is filled.
	"""
	if not frappe.db.exists("DocType", "Project"):
		return
	meta = frappe.get_meta("Project")
	if not (meta.has_field("ferum_p0_enabled") and meta.has_field("ferum_stage")):
		return

	# If any of the base Tender Won fields are missing -> disable P0 gates for that Project.
	where_parts: list[str] = []
	if meta.has_field("eis_etp_url"):
		where_parts.append("ifnull(eis_etp_url,'') = ''")
	if meta.has_field("tender_customer_name"):
		where_parts.append("ifnull(tender_customer_name,'') = ''")
	if meta.has_field("tender_price"):
		where_parts.append("ifnull(tender_price,0) = 0")
	if meta.has_field("tender_protocol_date"):
		where_parts.append("tender_protocol_date is null")
	if meta.has_field("tender_term_start"):
		where_parts.append("tender_term_start is null")
	if meta.has_field("tender_term_end"):
		where_parts.append("tender_term_end is null")

	if not where_parts:
		return

	frappe.db.sql(
		f"""
		update `tabProject`
		set ferum_p0_enabled = 0
		where ifnull(ferum_p0_enabled, 0) = 1
		  and ({' or '.join(where_parts)})
		"""
	)
	frappe.db.commit()
	frappe.clear_cache()
