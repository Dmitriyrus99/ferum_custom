from __future__ import annotations

import re

import frappe

LEGACY_DT = "Project Site Row"
TRUTH_DT = "Project Site"


_DRIVE_ID_RE = re.compile(r"/folders/([a-zA-Z0-9_-]{10,})")


def _drive_folder_id_from_url(url: str | None) -> str | None:
	url = str(url or "").strip()
	if not url:
		return None
	m = _DRIVE_ID_RE.search(url)
	if not m:
		return None
	return str(m.group(1)).strip() or None


def _project_contract(project: str) -> str | None:
	if not frappe.db.exists("DocType", "Project"):
		return None
	if not frappe.db.has_column("Project", "contract"):
		return None
	val = frappe.db.get_value("Project", project, "contract")
	val = str(val or "").strip()
	return val or None


def _project_company_customer(project: str) -> tuple[str | None, str | None]:
	if not frappe.db.exists("DocType", "Project"):
		return None, None
	fields: list[str] = []
	if frappe.db.has_column("Project", "company"):
		fields.append("company")
	if frappe.db.has_column("Project", "customer"):
		fields.append("customer")
	if not fields:
		return None, None
	row = frappe.db.get_value("Project", project, fields, as_dict=True) or {}
	company = str((row or {}).get("company") or "").strip() or None
	customer = str((row or {}).get("customer") or "").strip() or None
	return company, customer


def execute() -> None:
	"""Migrate legacy child rows -> truth Project Site.

	Strategy:
	- Legacy child rows live in `Project.project_sites` as DocType `Project Site Row`.
	- Truth doctype is `Project Site`.
	- We keep `name` the same as legacy row name to preserve backward compatibility for
	  `Service Request.project_site` links.

	Idempotent: safe to rerun.
	"""
	if not frappe.db.exists("DocType", LEGACY_DT):
		return
	if not frappe.db.exists("DocType", TRUTH_DT):
		return

	rows = frappe.get_all(
		LEGACY_DT,
		filters={"parenttype": "Project", "parentfield": "project_sites"},
		fields=[
			"name",
			"parent",
			"site_name",
			"address",
			"drive_folder_url",
			"default_engineer",
			"notes",
			"modified",
		],
		limit_page_length=200000,
	)
	if not rows:
		return

	created = 0
	updated = 0
	missing_contract = 0
	renamed = 0

	for r in rows:
		row_name = str(r.get("name") or "").strip()
		project = str(r.get("parent") or "").strip()
		if not row_name:
			continue

		legacy_key = f"project_site_row:{row_name}"
		if not frappe.db.exists(TRUTH_DT, row_name):
			# Backward-compatible repair:
			# earlier versions of this patch created truth records with naming series (PS-00001)
			# because `DocType Project Site` uses autoname; those records are tracked by `legacy_key`.
			existing = frappe.db.get_value(TRUTH_DT, {"legacy_key": legacy_key}, "name")
			existing = str(existing or "").strip() or None
			if existing and existing != row_name:
				try:
					frappe.rename_doc(TRUTH_DT, existing, row_name, force=True, ignore_permissions=True)
					renamed += 1
				except Exception:
					frappe.log_error(
						frappe.get_traceback(),
						"Rename Project Site to legacy row name failed",
					)
					continue

		if frappe.db.exists(TRUTH_DT, row_name):
			# Best-effort: backfill missing fields without overriding user changes.
			updates: dict[str, object] = {}
			contract = _project_contract(project) if project else None
			if contract and frappe.db.has_column(TRUTH_DT, "contract"):
				current = frappe.db.get_value(TRUTH_DT, row_name, "contract")
				if not current:
					updates["contract"] = contract
			if project and frappe.db.has_column(TRUTH_DT, "project"):
				current = frappe.db.get_value(TRUTH_DT, row_name, "project")
				if not current:
					updates["project"] = project
			if updates:
				frappe.db.set_value(TRUTH_DT, row_name, updates, update_modified=False)
				updated += 1
			continue

		contract = _project_contract(project) if project else None
		company, customer = _project_company_customer(project) if project else (None, None)
		drive_url = str(r.get("drive_folder_url") or "").strip() or None
		drive_id = _drive_folder_id_from_url(drive_url)

		doc_dict: dict[str, object] = {
			"doctype": TRUTH_DT,
			"name": row_name,
			"contract": contract,
			"project": project or None,
			"company": company,
			"customer": customer,
			"site_name": str(r.get("site_name") or "").strip() or "Объект",
			"address": str(r.get("address") or "").strip() or "Адрес уточняется",
			"drive_folder_url": drive_url,
			"drive_folder_id": drive_id,
			"default_engineer": str(r.get("default_engineer") or "").strip() or None,
			"notes": str(r.get("notes") or "").strip() or None,
			"legacy_key": legacy_key,
		}

		# If contract is missing, still create a placeholder row to preserve link integrity.
		ignore_mandatory = False
		if not contract:
			missing_contract += 1
			ignore_mandatory = True
			doc_dict["is_active"] = 0
			doc_dict["notes"] = (
				str(doc_dict.get("notes") or "") + "\n" if doc_dict.get("notes") else ""
			) + "migrated_without_contract=1"

		try:
			doc = frappe.get_doc(doc_dict)
			# Preserve legacy row `name` for backward compatibility:
			# - Service Request.project_site historically linked to child-row names
			# - DocType `Project Site` uses naming series by default, so we must use `set_name=...`
			doc.insert(
				ignore_permissions=True,
				ignore_mandatory=ignore_mandatory,
				set_name=row_name,
			)
			created += 1
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Migrate Project Site Row -> Project Site failed")
			continue

	frappe.db.commit()
	frappe.clear_cache()

	frappe.log_error(
		title="Ferum: migrate_project_site_row_to_truth",
		message=f"created={created} updated={updated} renamed={renamed} missing_contract={missing_contract}",
	)
