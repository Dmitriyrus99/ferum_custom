# Package Refactor Report — `ferum_custom`

Date: 2026-02-09

Scope: `/home/frappe/frappe-bench/apps/ferum_custom`

## 0) Executive summary

The repo has a **hybrid structure**:

- A Frappe app Python package root: `apps/ferum_custom/ferum_custom` (`import ferum_custom`).
- A Frappe “Module” folder with the same scrub name: `apps/ferum_custom/ferum_custom/ferum_custom`
  (`import ferum_custom.ferum_custom`) containing DocTypes, Reports, and module-scoped code.
- Legacy standalone entrypoints kept as **compatibility wrappers** (e.g. `backend/*`, `telegram_bot/*`) that
  delegate to canonical implementations under `ferum_custom/integrations/*`.

This layout is workable and matches how many Frappe apps evolve, but it creates confusion around import paths.
In this refactor we **standardize canonical imports**, keep backward compatibility, and add audit artifacts.

## 1) Current structure (high-level)

Canonical code locations:

- Frappe app hooks + services: `ferum_custom/*`
- Frappe Module artifacts (DocTypes/Reports): `ferum_custom/ferum_custom/*`
- Standalone services:
  - FastAPI backend: `ferum_custom/integrations/fastapi_backend/*`
  - Telegram bot: `ferum_custom/integrations/telegram_bot/*`

Compatibility wrapper locations:

- `backend/*` → `ferum_custom.integrations.fastapi_backend.*`
- `telegram_bot/*` → `ferum_custom.integrations.telegram_bot.*`
- `ferum_custom.ferum_custom.overrides.query_report` → `ferum_custom.overrides.query_report`

Audit artifacts (no secrets):

- `docs/audit/import_map_summary.json`
- `docs/audit/package_dirs.txt`
- `docs/audit/duplicated_package_segments.txt`
- `docs/audit/hooks_import_check.txt`
- `docs/audit/*_module_meta_import_failures.txt`

## 2) Findings

### 2.1 Duplicated package nesting

Detected duplicated consecutive segments (examples):

- `ferum_custom/ferum_custom/*` — expected due to Frappe module folder named the same as the app/module.
- `telegram_bot/telegram_bot/*` — historical wrapper package.

Full list: `docs/audit/duplicated_package_segments.txt`.

### 2.2 Import and dependency map

Static import scan (AST-based):

- Scanned modules: 236
- Files with imports: 183
- Missing internal imports: 0
- Strong cycles detected: 0 (module-level graph; best-effort resolution)

Summary: `docs/audit/import_map_summary.json`.

### 2.3 Critical runtime entrypoints (hooks)

Active hook targets were import-checked and all imports resolve:

- Doc events, permission hooks, scheduled tasks, overrides, whitelisted overrides.

Evidence: `docs/audit/hooks_import_check.txt`.

### 2.4 Frappe meta/import stability

For both sites:

- `test_site`
- `erpclone.ferumrus.ru`

All standard DocTypes in module **Ferum Custom** (`custom=0`) load successfully, and Query Reports execute
with empty filters (via the overridden report runner).

Evidence:

- `docs/audit/test_site_module_meta_import_failures.txt`
- `docs/audit/erpclone.ferumrus.ru_module_meta_import_failures.txt`

## 3) Changes implemented in this refactor

### 3.1 Normalize `query_report` override location

Problem:

- The canonical hook path is `ferum_custom.overrides.query_report.run`.
- The full implementation lived under `ferum_custom.ferum_custom.overrides.query_report`, requiring wrappers.

Change:

- Moved the implementation to `ferum_custom/overrides/query_report.py`.
- Converted `ferum_custom/ferum_custom/overrides/query_report.py` to a compatibility wrapper.

Result:

- Hook paths stay stable: `ferum_custom.overrides.query_report.run`.
- Backward-compatible imports continue to work: `ferum_custom.ferum_custom.overrides.query_report.run`.

## 4) Modified files (this change set)

- `ferum_custom/overrides/query_report.py`
- `ferum_custom/ferum_custom/overrides/query_report.py`
- `ferum_custom/ferum_custom/tests/test_query_report_override.py`
- `docs/audit/import_map_summary.json`
- `docs/audit/package_dirs.txt`
- `docs/audit/duplicated_package_segments.txt`
- `docs/audit/hooks_import_check.txt`
- `docs/audit/test_site_module_meta_import_failures.txt`
- `docs/audit/erpclone.ferumrus.ru_module_meta_import_failures.txt`
- `docs/package_refactor_report.md`

## 5) Validation executed

From `apps/ferum_custom`:

- `pre-commit run --all-files`
- `pre-commit run --all-files --hook-stage pre-push`

From bench root:

- `bench --site test_site migrate`
- `bench --site erpclone.ferumrus.ru migrate`
- `bench build --app ferum_custom`
- `bench --site test_site run-tests --app ferum_custom`

## 6) Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Import path drift (`ferum_custom.ferum_custom.*` vs `ferum_custom.*`) | runtime ImportError, broken hooks | keep shims/wrappers for historical imports; add import checks in audit |
| Query Report failures when UI sends empty filter dict | 500 errors on reports with `%(field)s` placeholders | override `frappe.desk.query_report.run` and pre-fill placeholders |

## 7) Rollback instructions

Rollback is reversible at code level:

1. Revert the Git commit(s) for this change set.
2. Run:
   - `bench --site <site> migrate`
   - restart bench processes (`bench restart` / process manager)
3. Clear caches if needed:
   - `bench --site <site> clear-cache`

## 8) Next steps (recommended)

Non-breaking improvements to continue the normalization:

1. Keep all “canonical” runtime entrypoints under `ferum_custom/*` (outer package), and limit
   `ferum_custom/ferum_custom/*` (module folder) to DocTypes/Reports/fixtures.
2. Add a small `bench execute`-friendly audit module (e.g., `ferum_custom.setup.audit`) to run:
   - doctype/report meta load check
   - hooks import check
   - system health checks (Vault/Drive/Telegram/FastAPI)
