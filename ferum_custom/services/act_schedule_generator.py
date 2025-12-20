from __future__ import annotations

import calendar
from datetime import date
from typing import Literal

import frappe
from frappe import _

from ferum_custom.services.contract_project_sync import ensure_project_for_contract, get_project_for_contract

Frequency = Literal["Monthly", "Quarterly", "Semiannual", "Annual"]


def _month_end(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def _iter_periods(start: date, end: date, step_months: int):
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        period_from = max(start, cursor)
        period_end = _month_end(_add_months(cursor, step_months - 1))
        period_to = min(end, period_end)
        yield (period_from, period_to)
        cursor = _add_months(cursor, step_months)


@frappe.whitelist()
def generate_act_schedule(contract: str, frequency: Frequency = "Monthly") -> list[str]:
    """Generate ActSchedule rows for a Contract.

    - Requires Contract to be Active (ensures Project exists via Contract→Project 1:1).
    - Splits contract_value equally if provided; otherwise planned_amount remains empty.
    """
    if not contract:
        frappe.throw(_("Contract is required."))

    contract_doc = frappe.get_doc("Contract", contract)
    if getattr(contract_doc, "status", None) != "Active":
        frappe.throw(_("Contract must be Active to generate Act Schedule."))

    ensure_project_for_contract(contract_doc)
    project = get_project_for_contract(contract_doc.name)
    if not project:
        frappe.throw(_("Project for Contract {0} not found.").format(frappe.bold(contract_doc.name)))

    start_date = getattr(contract_doc, "start_date", None)
    end_date = getattr(contract_doc, "end_date", None)
    if not start_date or not end_date:
        frappe.throw(_("Contract must have start_date and end_date to generate Act Schedule."))

    step_months_map = {"Monthly": 1, "Quarterly": 3, "Semiannual": 6, "Annual": 12}
    step_months = step_months_map.get(frequency)
    if not step_months:
        frappe.throw(_("Unsupported frequency: {0}").format(frequency))

    periods = list(_iter_periods(start_date, end_date, step_months))
    if not periods:
        return []

    contract_value = getattr(contract_doc, "contract_value", None)
    per_period_amount = None
    if contract_value:
        per_period_amount = float(contract_value) / len(periods)

    created: list[str] = []
    for period_from, period_to in periods:
        doc = frappe.new_doc("ActSchedule")
        doc.contract = contract_doc.name
        doc.project = project
        doc.period_from = period_from
        doc.period_to = period_to
        if per_period_amount is not None:
            doc.planned_amount = per_period_amount
        doc.insert(ignore_permissions=True)
        created.append(doc.name)

    return created
