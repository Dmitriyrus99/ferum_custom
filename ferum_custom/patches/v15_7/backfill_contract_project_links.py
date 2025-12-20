from __future__ import annotations

import frappe


def _dt_exists(dt: str) -> bool:
    return bool(dt and frappe.db.exists("DocType", dt))


def _service_request_dt() -> str | None:
    for dt in ("Service Request", "ServiceRequest"):
        if _dt_exists(dt):
            return dt
    return None


def _service_schedule_dt() -> str | None:
    for dt in ("Service Maintenance Schedule", "Maintenance Schedule", "MaintenanceSchedule"):
        if _dt_exists(dt):
            return dt
    return None


def _invoice_dt() -> str | None:
    return "Invoice" if _dt_exists("Invoice") else None


def _has_column(dt: str, col: str) -> bool:
    try:
        return frappe.db.has_column(dt, col)
    except Exception:
        return False


def _backfill_contract_on_service_request(sr_dt: str) -> None:
    if not _has_column(sr_dt, "contract") or not _has_column(sr_dt, "service_object"):
        return
    if not _dt_exists("ContractServiceObject"):
        return

    table = f"`tab{sr_dt}`"
    # Step 1: Fill contract only when exactly 1 active link exists for the service_object.
    frappe.db.sql(
        f"""
        update {table} sr
        set sr.contract = (
            select min(cso.contract)
            from `tabContractServiceObject` cso
            where cso.service_object = sr.service_object
              and cso.status = 'Active'
        )
        where ifnull(sr.contract, '') = ''
          and ifnull(sr.service_object, '') != ''
          and (
            select count(*)
            from `tabContractServiceObject` cso2
            where cso2.service_object = sr.service_object
              and cso2.status = 'Active'
          ) = 1
        """
    )

    # Step 2: If multiple active contracts exist, prefer same company (when company is present).
    if _has_column(sr_dt, "company") and frappe.db.has_column("Contract", "company"):
        frappe.db.sql(
            f"""
            update {table} sr
            set sr.contract = (
                select c.name
                from `tabContractServiceObject` cso
                join `tabContract` c on c.name = cso.contract
                where cso.service_object = sr.service_object
                  and cso.status = 'Active'
                  and ifnull(sr.company,'') != ''
                  and c.company = sr.company
                order by ifnull(c.start_date, '1900-01-01') desc, c.modified desc, c.name desc
                limit 1
            )
            where ifnull(sr.contract, '') = ''
              and ifnull(sr.service_object, '') != ''
              and ifnull(sr.company,'') != ''
              and (
                select count(*)
                from `tabContractServiceObject` cso2
                where cso2.service_object = sr.service_object
                  and cso2.status = 'Active'
              ) > 1
            """
        )

    # Step 3: Fallback to most recent contract by start_date/modified.
    frappe.db.sql(
        f"""
        update {table} sr
        set sr.contract = (
            select c.name
            from `tabContractServiceObject` cso
            join `tabContract` c on c.name = cso.contract
            where cso.service_object = sr.service_object
              and cso.status = 'Active'
            order by ifnull(c.start_date, '1900-01-01') desc, c.modified desc, c.name desc
            limit 1
        )
        where ifnull(sr.contract, '') = ''
          and ifnull(sr.service_object, '') != ''
          and (
            select count(*)
            from `tabContractServiceObject` cso2
            where cso2.service_object = sr.service_object
              and cso2.status = 'Active'
          ) > 1
        """
    )

    # Fill customer from contract
    if _has_column(sr_dt, "customer"):
        frappe.db.sql(
            f"""
            update {table} sr
            join `tabContract` c on c.name = sr.contract
            set sr.customer = c.party_name
            where ifnull(sr.contract, '') != ''
              and (ifnull(sr.customer, '') = '')
              and ifnull(c.party_type, '') in ('', 'Customer')
            """
        )

    # Fill standard Project link if field exists on SR and Project has contract column.
    if _has_column(sr_dt, "erpnext_project") and frappe.db.has_column("Project", "contract"):
        frappe.db.sql(
            f"""
            update {table} sr
            set sr.erpnext_project = (
                select p.name from `tabProject` p
                where p.contract = sr.contract
                limit 1
            )
            where ifnull(sr.contract, '') != ''
              and ifnull(sr.erpnext_project, '') = ''
            """
        )


def _backfill_contract_on_schedule(sched_dt: str) -> None:
    if not _has_column(sched_dt, "contract"):
        return
    if not _dt_exists("ContractServiceObject"):
        return

    table = f"`tab{sched_dt}`"
    # For schedules without contract, try infer from customer+service_project is unreliable; skip.
    # Only fill erpnext_project when contract already set.
    if _has_column(sched_dt, "erpnext_project") and frappe.db.has_column("Project", "contract"):
        frappe.db.sql(
            f"""
            update {table} s
            set s.erpnext_project = (
                select p.name from `tabProject` p
                where p.contract = s.contract
                limit 1
            )
            where ifnull(s.contract, '') != ''
              and ifnull(s.erpnext_project, '') = ''
            """
        )


def _backfill_invoice(invoice_dt: str) -> None:
    if not _has_column(invoice_dt, "contract"):
        return

    table = f"`tab{invoice_dt}`"
    if _has_column(invoice_dt, "erpnext_project") and frappe.db.has_column("Project", "contract"):
        frappe.db.sql(
            f"""
            update {table} i
            set i.erpnext_project = (
                select p.name from `tabProject` p
                where p.contract = i.contract
                limit 1
            )
            where ifnull(i.contract, '') != ''
              and ifnull(i.erpnext_project, '') = ''
            """
        )


def execute() -> None:
    sr_dt = _service_request_dt()
    if sr_dt:
        _backfill_contract_on_service_request(sr_dt)

    sched_dt = _service_schedule_dt()
    if sched_dt:
        _backfill_contract_on_schedule(sched_dt)

    inv_dt = _invoice_dt()
    if inv_dt:
        _backfill_invoice(inv_dt)

    frappe.db.commit()
    frappe.clear_cache()
