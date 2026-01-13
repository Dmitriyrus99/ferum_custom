from __future__ import annotations

from ferum_custom.patches.v15_9.backfill_project_sites_from_service_objects import execute as _execute


def execute() -> None:
	# Rerun backfill using direct child inserts (the original patch might have been blocked by P0 gates).
	_execute()

