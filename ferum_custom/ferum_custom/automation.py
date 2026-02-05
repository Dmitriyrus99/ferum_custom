from __future__ import annotations

import logging

import frappe

logger = logging.getLogger("ferum.automation")


def enqueue_daily_drive_backfill_small(*, limit: int = 10, company: str | None = None) -> None:
	"""Enqueue a small daily backfill for missing Project.drive_folder_url values."""
	if frappe.flags.in_test:
		return

	frappe.enqueue(
		"ferum_custom.ferum_custom.automation._drive_backfill_small",
		queue="long",
		job_name="Ferum: drive backfill (small)",
		kwargs={"limit": int(limit or 10), "company": (company or "").strip() or None},
		timeout=60 * 60,
	)


def enqueue_weekly_full_backup() -> None:
	"""Enqueue a weekly full site backup (db + files)."""
	if frappe.flags.in_test:
		return

	frappe.enqueue(
		"ferum_custom.ferum_custom.automation._run_weekly_full_backup",
		queue="long",
		job_name="Ferum: weekly full backup",
		timeout=60 * 60 * 6,
	)


def _drive_backfill_small(*, limit: int = 10, company: str | None = None) -> None:
	frappe.set_user("Administrator")

	try:
		from ferum_custom.api.project_drive import ensure_drive_folders
		from ferum_custom.integrations.google_drive_folders import root_folder_id
	except Exception:
		frappe.log_error(title="Ferum: automation imports", message=frappe.get_traceback())
		return

	if not root_folder_id():
		logger.warning("Google Drive is not configured (missing root folder id); skipping backfill.")
		return

	if not frappe.db.has_column("Project", "drive_folder_url"):
		logger.warning("Project.drive_folder_url is missing; skipping backfill.")
		return

	filters: dict[str, object] = {}
	if company and frappe.db.has_column("Project", "company"):
		filters["company"] = company

	projects = frappe.get_all(
		"Project",
		filters=filters,
		or_filters=[{"drive_folder_url": ["=", ""]}, {"drive_folder_url": ["is", "not set"]}],
		pluck="name",
		limit=int(limit or 10),
	)

	if not projects:
		return

	for p in projects:
		try:
			ensure_drive_folders(p)
		except Exception:
			frappe.log_error(
				title=f"Ferum: drive backfill failed ({p})",
				message=frappe.get_traceback(),
			)


def _run_weekly_full_backup() -> None:
	frappe.set_user("Administrator")
	try:
		from frappe.utils import backups

		backups.new_backup(ignore_files=False, compress=True, force=True)
	except Exception:
		frappe.log_error(title="Ferum: weekly full backup failed", message=frappe.get_traceback())
