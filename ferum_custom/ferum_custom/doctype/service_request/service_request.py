from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now

from ferum_custom.config.settings import get_settings
from ferum_custom.config.types import parse_int
from ferum_custom.notifications import send_telegram_notification_to_fastapi
from ferum_custom.utils import project_sites


class ServiceRequest(Document):
	def validate(self):
		self._sync_source_timestamps()
		self._sync_contract_customer_project()
		self._validate_workflow_transitions()
		self._calculate_duration_hours()
		self._calculate_sla_deadline()
		self._validate_reported_source_evidence()

	def on_update(self):
		self._check_sla_breach()

	def _service_object_dt(self) -> str:
		if frappe.db.exists("DocType", "Service Object"):
			return "Service Object"
		return "ServiceObject"

	def _sync_customer_company_from_project(self) -> None:
		if not self.meta.has_field("erp_project"):
			return

		project = str(getattr(self, "erp_project", None) or "").strip()
		if not project:
			return

		if not frappe.db.exists("Project", project):
			frappe.throw(_("Project not found: {0}.").format(frappe.bold(project)))

		fields: list[str] = []
		if frappe.db.has_column("Project", "customer") and self.meta.has_field("customer"):
			fields.append("customer")
		if frappe.db.has_column("Project", "company") and self.meta.has_field("company"):
			fields.append("company")

		if not fields:
			return

		row = frappe.db.get_value("Project", project, fields, as_dict=True) or {}
		if not isinstance(row, dict):
			return

		if self.meta.has_field("customer") and row.get("customer"):
			self.customer = row.get("customer")

		# `company` is mandatory; prefer Project.company if not set.
		if self.meta.has_field("company") and not getattr(self, "company", None) and row.get("company"):
			self.company = row.get("company")

	def _validate_project_site_belongs_to_project(self) -> None:
		if not self.meta.has_field("project_site"):
			return
		project_site = str(getattr(self, "project_site", None) or "").strip()
		if not project_site:
			return
		erp_project = str(getattr(self, "erp_project", None) or "").strip()

		# Accept both truth and legacy row doctypes during migration/cutover.
		truth_exists = frappe.db.exists(project_sites.truth_doctype(), project_site)
		row_dt = project_sites.legacy_row_doctype()
		legacy_exists = bool(row_dt and frappe.db.exists(row_dt, project_site))
		if not truth_exists and not legacy_exists:
			frappe.throw(_("Project Site not found: {0}.").format(frappe.bold(project_site)))

		if erp_project and not project_sites.site_belongs_to_project(site=project_site, project=erp_project):
			frappe.throw(
				_("Project Site {0} does not belong to Project {1}.").format(
					frappe.bold(project_site), frappe.bold(erp_project)
				)
			)

	def _sync_contract_customer_project(self) -> None:
		# New model: Service Request -> ERPNext Project + Project Site.
		self._sync_customer_company_from_project()
		self._validate_project_site_belongs_to_project()

		# If contract is not set but service_object is known, try to infer contract from active link.
		if (
			not getattr(self, "contract", None)
			and getattr(self, "service_object", None)
			and self.meta.has_field("contract")
		):
			links = frappe.get_all(
				"ContractServiceObject",
				filters={"service_object": self.service_object, "status": "Active"},
				pluck="contract",
			)
			self.contract = _pick_contract_for_service_object(
				service_object=self.service_object,
				contracts=links,
				company=getattr(self, "company", None),
			)

		if getattr(self, "contract", None):
			contract = frappe.get_doc("Contract", self.contract)
			if contract.party_type and contract.party_type != "Customer":
				frappe.throw(_("Contract party_type must be Customer."))

			if contract.party_name:
				self.customer = contract.party_name

			if frappe.db.has_column("Project", "contract"):
				project = frappe.db.get_value("Project", {"contract": contract.name}, "name")
				if project and self.meta.has_field("erp_project"):
					self.erp_project = project
				if project and self.meta.has_field("erpnext_project"):
					self.erpnext_project = project

			if getattr(self, "service_object", None):
				so_customer = frappe.db.get_value(self._service_object_dt(), self.service_object, "customer")
				if so_customer and contract.party_name and so_customer != contract.party_name:
					frappe.throw(
						_("Service Object customer {0} must match Contract customer {1}.").format(
							frappe.bold(so_customer), frappe.bold(contract.party_name)
						)
					)

	def _validate_workflow_transitions(self) -> None:
		if not self.meta.has_field("status") or self.is_new():
			return

		old_status = frappe.db.get_value(self.doctype, self.name, "status")
		if not old_status or old_status == self.status:
			return

		if old_status == "Open" and self.status == "In Progress":
			if self.meta.has_field("assigned_to") and not getattr(self, "assigned_to", None):
				frappe.throw(_("Cannot set status to 'In Progress' without assigning an engineer."))
			return

		if old_status == "In Progress" and self.status == "Completed":
			if self.meta.has_field("linked_report") and not getattr(self, "linked_report", None):
				frappe.throw(_("Cannot set status to 'Completed' without linking a Service Report."))
			return

		if self.status == "Closed":
			if (
				self.meta.has_field("is_billable")
				and int(getattr(self, "is_billable", 0) or 0) == 1
				and self.meta.has_field("linked_report")
				and not getattr(self, "linked_report", None)
			):
				frappe.throw(_("Billable request requires linked Service Report before closing."))

	def _calculate_duration_hours(self) -> None:
		if not self.meta.has_field("duration_hours"):
			return

		start = getattr(self, "actual_start_datetime", None)
		end = getattr(self, "actual_end_datetime", None)
		if not start or not end:
			return

		try:
			delta = get_datetime(end) - get_datetime(start)
			self.duration_hours = round(delta.total_seconds() / 3600.0, 2)
		except Exception:
			return

	def _calculate_sla_deadline(self) -> None:
		if not self.meta.has_field("sla_deadline"):
			return

		if getattr(self, "status", None) == "Cancelled":
			return

		base = (
			getattr(self, "reported_datetime", None)
			or getattr(self, "registered_datetime", None)
			or getattr(self, "creation", None)
		)
		if not base:
			return

		typ = str(getattr(self, "type", "") or "").strip()
		priority = str(getattr(self, "priority", "") or "").strip()
		base_dt = get_datetime(base)

		if typ == "Emergency" and priority == "High":
			self.sla_deadline = add_to_date(base_dt, hours=4)
		elif typ == "Emergency" and priority == "Medium":
			self.sla_deadline = add_to_date(base_dt, hours=8)
		elif typ in {"Routine Maintenance", "Routine"} and priority == "High":
			self.sla_deadline = add_to_date(base_dt, days=1)
		else:
			self.sla_deadline = add_to_date(base_dt, days=3)

	def _check_sla_breach(self) -> None:
		if not self.meta.has_field("sla_deadline"):
			return

		if getattr(self, "status", None) in {"Completed", "Closed", "Cancelled"}:
			return

		deadline = getattr(self, "sla_deadline", None)
		if not deadline or not _is_past_deadline(deadline):
			return

		cache = frappe.cache()
		cache_key = _cache_sla_key(self.name, deadline)
		if cache and cache.get_value(cache_key):
			return
		if cache:
			cache.set_value(cache_key, "1", expires_in_sec=6 * 60 * 60)

		title = getattr(self, "title", "") or ""
		message = (
			f"SLA for Service Request {self.name} has been breached! "
			f"Title: {title}. Priority: {getattr(self, 'priority', None)}. Due: {deadline}"
		)
		frappe.log_error(message, "SLA Breach Alert")
		try:
			frappe.msgprint(_(message), alert=True, indicator="red")
		except Exception:
			pass
		_notify_sla_breach(message)

	def _sync_source_timestamps(self) -> None:
		"""Fill registration/source defaults in a backward-compatible way."""
		if self.meta.has_field("registered_datetime") and not getattr(self, "registered_datetime", None):
			# Use a deterministic value for inserts; for older records keep empty.
			if self.is_new():
				self.registered_datetime = now()

		if self.meta.has_field("source_channel") and not getattr(self, "source_channel", None):
			# Default for desk inserts; bot/API can override explicitly.
			self.source_channel = "ERP Desk"

	def _validate_reported_source_evidence(self) -> None:
		"""When reported time differs from registered time for external sources, require evidence."""
		if not (
			self.meta.has_field("reported_datetime")
			and self.meta.has_field("registered_datetime")
			and self.meta.has_field("source_channel")
		):
			return

		reported = getattr(self, "reported_datetime", None)
		registered = getattr(self, "registered_datetime", None)
		if not reported or not registered:
			return

		try:
			reported_dt = get_datetime(reported)
			registered_dt = get_datetime(registered)
		except Exception:
			return

		if abs((reported_dt - registered_dt).total_seconds()) < 1:
			return

		source = str(getattr(self, "source_channel", "") or "").strip()
		external_sources = {"Email", "Phone", "EIS", "Other"}
		if source not in external_sources:
			return

		ref = (
			str(getattr(self, "source_reference", "") or "").strip()
			if self.meta.has_field("source_reference")
			else ""
		)
		evidence = (
			str(getattr(self, "source_evidence_file", "") or "").strip()
			if self.meta.has_field("source_evidence_file")
			else ""
		)
		if ref or evidence:
			return

		frappe.throw(
			_(
				"Для внешних источников при отличии 'Дата обращения' от 'Зарегистрировано в ERP' "
				"нужно заполнить 'Источник (reference)' или приложить 'Подтверждение (файл)'."
			)
		)


def _pick_contract_for_service_object(
	*, service_object: str, contracts: list[str], company: str | None
) -> str | None:
	"""Deterministic inference when Service Object can belong to multiple active contracts.

	Priority:
	1) If only one contract -> use it
	2) If company is known -> choose contract with same company
	3) Choose most recent by (start_date desc, modified desc, name desc)
	If still ambiguous/empty -> return None (user must select).
	"""
	contracts = [c for c in contracts if c]
	if not contracts:
		return None
	if len(contracts) == 1:
		return contracts[0]

	if company and frappe.db.has_column("Contract", "company"):
		same_company = frappe.get_all(
			"Contract",
			filters={"name": ["in", contracts], "company": company},
			pluck="name",
		)
		if len(same_company) == 1:
			return same_company[0]
		if len(same_company) > 1:
			contracts = same_company

	# Prefer most recent contract
	row = frappe.db.sql(
		"""
        select name
        from tabContract
        where name in %(names)s
        order by ifnull(start_date, '1900-01-01') desc, modified desc, name desc
        limit 1
        """,
		{"names": tuple(contracts)},
	)
	return row[0][0] if row else None


def _get_int_setting(*keys: str) -> int | None:
	settings = get_settings()
	return parse_int(settings.get(*keys))


def _get_setting(*keys: str) -> str | None:
	settings = get_settings()
	return settings.get(*keys)


def _dt_now() -> object:
	return get_datetime(now())


def _is_past_deadline(deadline: object) -> bool:
	try:
		return get_datetime(deadline) < _dt_now()
	except Exception:
		return False


def _cache_sla_key(name: str, deadline: object) -> str:
	return f"ferum:sla_breach_notified:{name}:{deadline}"


def _notify_sla_breach(message: str) -> None:
	chat_id = _get_int_setting("ferum_telegram_default_chat_id", "FERUM_TELEGRAM_DEFAULT_CHAT_ID")
	if chat_id:
		send_telegram_notification_to_fastapi(chat_id, message)

	recipient_email = _get_setting("ferum_sla_alert_email", "FERUM_SLA_ALERT_EMAIL")
	if recipient_email:
		frappe.sendmail(
			recipients=recipient_email,
			subject="SLA Breach Alert",
			message=message,
		)
