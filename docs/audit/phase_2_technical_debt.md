# PHASE 2 — Technical Debt (Implementation Report)

Date: 2026-02-05

## 1) Scope & Goals

Phase 2 focuses on stabilizing the “legacy → new model” transition without breaking compatibility:

- Reduce reliance on legacy `Service Project` / `Service Object` where the new model is `Project` + `Project Site`.
- Make legacy entities effectively **read-only** (admin-only) to prevent drift.
- Align key controllers/reports with the current schema (prevent “silent” inconsistencies).
- Add regression tests for the new invariants.

Constraints honored:

- Backward compatible: legacy fields remain (hidden) and are still considered where needed.
- Idempotent migrations only.
- Tests added and executed.

## 2) Scan Summary (What Was Found)

Key findings confirmed during Phase 2 scan:

- “Service Requests by Project” and “Invoices by Project” were implemented as **Script Reports** but still
  referenced legacy `Service Project` / legacy `project` field.
- `Service Request` controller logic was partially out of sync with current schema:
  - did not consistently sync `customer`/`company` from `erp_project` (new model)
  - did not validate that `project_site` belongs to `erp_project`
- Legacy `Service Object` had no global access guard similar to `Service Project` (risk of accidental edits).

## 3) Dependency & Risk Map (Phase 2)

| Area | Risk | Fix |
|---|---|---|
| Legacy doctypes editable | users re-introduce legacy references | deny mutations via `DocPerm` patch + `has_permission` hook |
| Reports tied to legacy model | UX confusion, wrong filters, missed data | update Script Reports to `Project` and migrated fields |
| Service Request integrity | cross-project site selection, missing company/customer | server-side sync + strict validation |

## 4) Patch Set (Code Changes)

### Legacy read-only enforcement

- `ferum_custom/security/service_object_permissions.py` — denies access to legacy `Service Object` for non-admin.
- `ferum_custom/hooks.py` — wires `Service Object` permission hook.
- Patch: `ferum_custom/patches/v15_9/disable_legacy_service_object_mutations.py` (registered in `patches.txt`)
  disables create/write/delete/submit/cancel/amend in `DocPerm` for non-admin roles (idempotent).

### New model alignment

- `ferum_custom/ferum_custom/doctype/service_request/service_request.py`
  - sync `customer` + `company` from `erp_project` (Project)
  - validate `project_site` belongs to `erp_project`
  - keep legacy contract/service-object inference only when legacy fields exist

### Reports migrated to `Project`

- `ferum_custom/ferum_custom/report/service_requests_by_project/*`
  - `Project` filter + `ifnull(erp_project, erpnext_project)` column
- `ferum_custom/ferum_custom/report/invoices_by_project/*`
  - `Project` filter + `erpnext_project` column (migrated/custom field)

## 5) Tests & Validation

Added Frappe regression tests:

- `ferum_custom/ferum_custom/doctype/service_request/test_service_request.py`
  - verifies server-side sync of `company`/`customer`
  - verifies `project_site` cannot belong to another project

Validation executed:

- `bench --site test_site run-tests --app ferum_custom --doctype "Service Request" --skip-test-records`
- `bench --site test_site migrate` (applied patch `disable_legacy_service_object_mutations`)
- `pytest` (app repo backend suite) — passed
- `pre-commit run --all-files` — passed

## 6) Operator Notes

- Legacy doctypes are now effectively admin-only; end users should use:
  - `Project` + `Project Sites` report (workspaces already point there)
  - `Service Request.erp_project` + `Service Request.project_site`
- If you need to temporarily allow access for a migration task:
  - use Administrator and/or run controlled scripts with `ignore_permissions=True`
