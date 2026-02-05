from __future__ import annotations

import frappe

from ferum_custom.services.contract_project_sync import sync_project_from_contract


def _exists(dt: str) -> bool:
	return bool(dt and frappe.db.exists("DocType", dt))


def _ensure_customer(link_value: str, *, company: str | None = None) -> str:
	"""Ensure Customer exists and return its name.

	If the referenced Customer name doesn't exist, create a minimal Customer and return its new name.
	"""
	if not link_value:
		raise ValueError("Empty customer link value")
	if frappe.db.exists("Customer", link_value):
		return link_value

	# Pick sane defaults from existing masters
	customer_group = frappe.db.get_value(
		"Customer Group", {"name": ["like", "%All%"]}, "name"
	) or frappe.db.get_value("Customer Group", {}, "name")
	territory = frappe.db.get_value("Territory", {"name": ["like", "%All%"]}, "name") or frappe.db.get_value(
		"Territory", {}, "name"
	)

	doc = frappe.new_doc("Customer")
	doc.customer_name = link_value
	if customer_group and doc.meta.has_field("customer_group"):
		doc.customer_group = customer_group
	if territory and doc.meta.has_field("territory"):
		doc.territory = territory
	if doc.meta.has_field("customer_type"):
		doc.customer_type = "Company"

	# Best-effort: company is not a standard field on Customer in ERPNext, ignore if absent.
	doc.insert(ignore_permissions=True)
	return doc.name


def _repair_legacy_customer_links(service_project_name: str, new_customer: str) -> None:
	# Update Service Project.customer to real Customer name
	frappe.db.set_value("Service Project", service_project_name, "customer", new_customer)

	# Update Service Objects under this project
	if frappe.db.exists("DocType", "Service Object") and frappe.db.has_column("Service Object", "project"):
		frappe.db.sql(
			"""
            update `tabService Object`
            set customer = %s
            where `project` = %s
              and (ifnull(customer,'') = '' or customer != %s)
            """,
			(new_customer, service_project_name, new_customer),
		)

	# Update Service Requests under this project (legacy field name is `project`)
	if frappe.db.exists("DocType", "Service Request") and frappe.db.has_column("Service Request", "project"):
		if frappe.db.has_column("Service Request", "customer"):
			frappe.db.sql(
				"""
                update `tabService Request`
                set customer = %s
                where `project` = %s
                  and (ifnull(customer,'') = '' or customer != %s)
                """,
				(new_customer, service_project_name, new_customer),
			)


def _get_or_create_contract_for_service_project(sp_name: str) -> str | None:
	sp = frappe.get_doc("Service Project", sp_name)

	if not sp.customer:
		frappe.log_error(
			f"Skip Service Project {sp.name}: empty Customer",
			"Service Project -> Contract migration",
		)
		return None

	if not frappe.db.exists("Customer", sp.customer):
		new_customer = _ensure_customer(sp.customer, company=getattr(sp, "company", None))
		_repair_legacy_customer_links(sp.name, new_customer)
		sp.customer = new_customer

	# Idempotency: reuse contract by contract_code == service project name
	if frappe.db.has_column("Contract", "contract_code"):
		existing = frappe.db.get_value("Contract", {"contract_code": sp.name}, "name")
		if existing:
			return existing

	contract = frappe.new_doc("Contract")
	contract.party_type = "Customer"
	contract.party_name = sp.customer

	if frappe.db.has_column("Contract", "company"):
		if sp.company and frappe.db.exists("Company", sp.company):
			contract.company = sp.company

	if frappe.db.has_column("Contract", "document_mode"):
		contract.document_mode = "UPD_ONLY"
	if frappe.db.has_column("Contract", "submission_channel"):
		contract.submission_channel = "OTHER"
	if frappe.db.has_column("Contract", "acts_deadline_day"):
		contract.acts_deadline_day = 5

	contract.start_date = sp.start_date
	contract.end_date = sp.end_date or sp.start_date

	if frappe.db.has_column("Contract", "contract_value"):
		contract.contract_value = sp.total_amount

	# Required on this DB
	if frappe.db.has_column("Contract", "contract_year"):
		contract.contract_year = (
			contract.start_date.year if contract.start_date else frappe.utils.now_datetime().year
		)

	contract.contract_terms = f"Migrated from Service Project {sp.name}"

	if frappe.db.has_column("Contract", "contract_code"):
		contract.contract_code = sp.name

	# Bypass workflow validations during patch
	frappe.flags.in_install = "frappe"
	contract.insert(ignore_permissions=True)
	frappe.flags.in_install = None

	# Activate to fit new model (Project is created for Active contracts)
	contract.db_set("status", "Active")
	contract.reload()
	return contract.name


def _ensure_project_for_contract(contract_name: str, service_project_name: str) -> str | None:
	contract = frappe.get_doc("Contract", contract_name)
	sp = frappe.get_doc("Service Project", service_project_name)

	# Prefer reusing existing ERP Project linked from Service Project, if it exists and is free.
	if getattr(sp, "erp_project", None) and frappe.db.exists("Project", sp.erp_project):
		project = frappe.get_doc("Project", sp.erp_project)
		if getattr(project, "contract", None) in (None, "", contract_name):
			project.contract = contract_name
			sync_project_from_contract(contract, project)
			project.save(ignore_permissions=True)
			return project.name

	# Otherwise, use ensure_project_for_contract logic indirectly by creating a Project if missing.
	existing = frappe.db.get_value("Project", {"contract": contract_name}, "name")
	if existing:
		return existing

	project = frappe.new_doc("Project")
	project.project_name = sp.project_name or sp.name
	if hasattr(project, "project_type"):
		if frappe.db.exists("Project Type", "External"):
			project.project_type = "External"
		else:
			fallback = frappe.db.get_value("Project Type", {}, "name")
			if fallback:
				project.project_type = fallback
	project.contract = contract_name
	sync_project_from_contract(contract, project)
	project.insert(ignore_permissions=True)
	return project.name


def _link_objects(contract_name: str, service_project_name: str) -> None:
	sp = frappe.get_doc("Service Project", service_project_name)
	for row in sp.get("objects") or []:
		if not row.service_object:
			continue
		if frappe.db.exists(
			"ContractServiceObject",
			{"contract": contract_name, "service_object": row.service_object},
		):
			continue
		doc = frappe.new_doc("ContractServiceObject")
		doc.contract = contract_name
		doc.service_object = row.service_object
		doc.status = "Active"
		doc.insert(ignore_permissions=True)


def _backfill_refs(service_project_name: str, contract_name: str, erp_project: str | None) -> None:
	# Service Request
	if (
		_exists("Service Request")
		and frappe.db.has_column("Service Request", "project")
		and frappe.db.has_column("Service Request", "contract")
	):
		frappe.db.sql(
			"""
            update `tabService Request`
            set contract = %s
            where ifnull(contract,'')=''
              and `project` = %s
            """,
			(contract_name, service_project_name),
		)
		if erp_project and frappe.db.has_column("Service Request", "erpnext_project"):
			frappe.db.sql(
				"""
                update `tabService Request`
                set erpnext_project = %s
                where ifnull(contract,'')=%s
                  and ifnull(erpnext_project,'')=''
                """,
				(erp_project, contract_name),
			)

	# Service Maintenance Schedule
	if (
		_exists("Service Maintenance Schedule")
		and frappe.db.has_column("Service Maintenance Schedule", "service_project")
		and frappe.db.has_column("Service Maintenance Schedule", "contract")
	):
		frappe.db.sql(
			"""
            update `tabService Maintenance Schedule`
            set contract = %s
            where ifnull(contract,'')=''
              and `service_project` = %s
            """,
			(contract_name, service_project_name),
		)
		if erp_project and frappe.db.has_column("Service Maintenance Schedule", "erpnext_project"):
			frappe.db.sql(
				"""
                update `tabService Maintenance Schedule`
                set erpnext_project = %s
                where ifnull(contract,'')=%s
                  and ifnull(erpnext_project,'')=''
                """,
				(erp_project, contract_name),
			)

	# Invoice (custom)
	if (
		_exists("Invoice")
		and frappe.db.has_column("Invoice", "project")
		and frappe.db.has_column("Invoice", "contract")
	):
		frappe.db.sql(
			"""
            update `tabInvoice`
            set contract = %s
            where ifnull(contract,'')=''
              and `project` = %s
            """,
			(contract_name, service_project_name),
		)
		if erp_project and frappe.db.has_column("Invoice", "erpnext_project"):
			frappe.db.sql(
				"""
                update `tabInvoice`
                set erpnext_project = %s
                where ifnull(contract,'')=%s
                  and ifnull(erpnext_project,'')=''
                """,
				(erp_project, contract_name),
			)


def execute() -> None:
	if not _exists("Service Project") or not _exists("Contract"):
		return

	service_projects = frappe.get_all("Service Project", pluck="name")
	for sp_name in service_projects:
		contract_name = _get_or_create_contract_for_service_project(sp_name)
		if not contract_name:
			continue
		erp_project = _ensure_project_for_contract(contract_name, sp_name)
		_link_objects(contract_name, sp_name)
		_backfill_refs(sp_name, contract_name, erp_project)

	frappe.db.commit()
	frappe.clear_cache()
