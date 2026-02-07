# Ferum Custom — Package/Directory Normalization Report

Date: 2026-02-07 (updated; initial refactor 2026-02-05)

Scope: `apps/ferum_custom` (custom app repo) — Python package layout and imports.

## Executive Summary

The repo contained a mix of:

- **Frappe module packages** (e.g. `ferum_custom.ferum_custom.*`) which are *expected* when a Module’s scrubbed name
  equals the app name (`Ferum Custom` → `ferum_custom`).
- **Implicit namespace packages** (directories with `.py` files but **no** `__init__.py`) used for active code.
- **Legacy / empty directories** that increased confusion during debugging and refactors.

This change set normalizes active Python code into **explicit packages** (adds missing `__init__.py`), removes
unused/legacy placeholders, and keeps Frappe import paths backward-compatible.

Update (2026-02-07): The standalone **Telegram bot** was consolidated under the installed app package
(`ferum_custom.integrations.telegram_bot`) to avoid fragile runtime entrypoints relying on implicit namespace packages
like `apps.*`. Compatibility wrappers are kept for historical import paths and run commands.

No functional modules were removed.

## 1) Scan Results (Before)

### 1.1 Duplicated nesting

`ferum_custom/ferum_custom` exists because Frappe resolves DocType/report controllers by:

`<app>.<module>.doctype.<doctype>...`

If `Module Def = "Ferum Custom"` then `scrub(module) = "ferum_custom"`, producing:

- `ferum_custom.ferum_custom.doctype...`

So this “duplicate name” is **structural and correct** for Frappe apps with a single module named like the app.

### 1.2 Inconsistent package layout (implicit namespace packages)

The following folders contained Python modules but had **no** `__init__.py` (PEP 420 namespaces):

- `ferum_custom/integrations/`
- `ferum_custom/security/`
- `ferum_custom/services/`
- `ferum_custom/utils/`
- `backend/bot/`
- Telegram bot runtime entrypoint depended on implicit namespaces (`apps.ferum_custom...`) from bench root.

Namespace packages are workable, but are fragile across tooling / editable installs and make refactors riskier.

### 1.3 Redundant/legacy package roots

- `ferum_custom/doctype/README.md` — legacy placeholder directory (not used by Frappe module loading).
- `ferum_custom/ferum/__init__.py` — unused package (no references; no Module Def in DB).
- Untracked empty directories existed in the working tree:
  - `ferum_custom/report/*` (empty)
  - `ferum_custom/notifications/` (empty; collided with `notifications.py`)

## 2) Import & Dependency Map (Snapshot)

Static AST scan:

- Python files scanned: **204**
- Internal import statements found (absolute-only): **57** (unique modules: **19**)
- Broken internal import targets on disk: **0**
- Top external dependencies by import frequency:
  - `frappe` (dominant), `aiogram`, `fastapi`, `httpx`, `googleapiclient`, `requests`
- Top internal import hotspots:
  - `ferum_custom.config.settings` (shared config)
  - `ferum_custom.integrations.google_drive_folders`
  - `ferum_custom.api.project_drive`
  - `ferum_custom.utils.role_resolution`
- Coarse package graph (2-level) SCC analysis:
  - **No cycles detected** (0 strongly connected components with size > 1)

## 3) Implemented Normalized Structure (After)

### 3.1 What changed (filesystem)

Before (relevant excerpt):

```
apps/ferum_custom/
  backend/
    bot/                 (no __init__.py)
  ferum_custom/
    doctype/README.md    (legacy placeholder)
    ferum/__init__.py    (unused)
    integrations/        (no __init__.py)
    security/            (no __init__.py)
    services/            (no __init__.py)
    utils/               (no __init__.py)
    report/              (empty; untracked)
    notifications/       (empty; untracked; name collision with notifications.py)
    ferum_custom/        (Frappe module package)
      doctype/...
      report/...
```

After (relevant excerpt):

```
apps/ferum_custom/
  backend/
    bot/__init__.py
  ferum_custom/
    integrations/__init__.py
    integrations/telegram_bot/
      __init__.py
      __main__.py
      main.py
      selftest.py
      frappe.py
      handlers/...
    security/__init__.py
    services/__init__.py
    utils/__init__.py
    notifications.py
    ferum_custom/        (Frappe module package; unchanged)
      doctype/...
      report/...
  telegram_bot/          (compatibility wrappers; preserved)
    main.py
    selftest.py
    telegram_bot/...
```

Added explicit package markers:

- `backend/bot/__init__.py`
- `backend/tests/__init__.py`
- `ferum_custom/integrations/__init__.py`
- `ferum_custom/security/__init__.py`
- `ferum_custom/services/__init__.py`
- `ferum_custom/utils/__init__.py`

Removed unused placeholders:

- `ferum_custom/doctype/README.md`
- `ferum_custom/ferum/__init__.py`

Workspace hygiene (untracked empties removed):

- `ferum_custom/report/`
- `ferum_custom/notifications/`
- `ferum_custom/doctype/`
- `ferum_custom/ferum/`

Changed files (git-tracked):

- Added: `backend/bot/__init__.py`
- Added: `backend/tests/__init__.py`
- Added: `ferum_custom/integrations/__init__.py`
- Added: `ferum_custom/security/__init__.py`
- Added: `ferum_custom/services/__init__.py`
- Added: `ferum_custom/utils/__init__.py`
- Added: `docs/package_refactor_report.md`
- Deleted: `ferum_custom/doctype/README.md`
- Deleted: `ferum_custom/ferum/__init__.py`

Update (2026-02-07) changed files (Telegram bot consolidation):

- Moved: `telegram_bot/main.py` → `ferum_custom/integrations/telegram_bot/main.py`
- Moved: `telegram_bot/selftest.py` → `ferum_custom/integrations/telegram_bot/selftest.py`
- Moved: `telegram_bot/telegram_bot/frappe.py` → `ferum_custom/integrations/telegram_bot/frappe.py`
- Moved: `telegram_bot/telegram_bot/settings.py` → `ferum_custom/integrations/telegram_bot/settings.py`
- Moved: `telegram_bot/telegram_bot/handlers/*` → `ferum_custom/integrations/telegram_bot/handlers/*`
- Added: `ferum_custom/integrations/telegram_bot/__main__.py`
- Added wrappers:
  - `telegram_bot/main.py`
  - `telegram_bot/selftest.py`
  - `telegram_bot/telegram_bot/*`
- Updated tests: `backend/tests/test_contract_frappe_api.py`
- Updated docs:
  - `RUN.md`
  - `DEPLOYMENT_GUIDE.md`
  - `docs/runbooks/telegram_bot.md`
  - `docs/runbooks/product_readiness_checklist.md`
  - `docs/audit/phase_1_vault_config.md`
  - `docs/audit/phase_3_scaling.md`

### 3.2 Import paths

No production import paths were changed.

Key Frappe module paths remain:

- `ferum_custom.ferum_custom.doctype.*`
- `ferum_custom.ferum_custom.report.*`

Telegram bot canonical paths:

- `ferum_custom.integrations.telegram_bot.*`

Telegram bot compatibility paths (kept):

- `telegram_bot.telegram_bot.*`
- `apps.ferum_custom.telegram_bot.*` (bench Procfile/supervisor previously used this)

## 4) Validation Results

Executed after refactor:

- `cd apps/ferum_custom && pytest` → **passed** (9 tests)
- `cd apps/ferum_custom && pre-commit run --all-files` → **passed**
- `cd apps/ferum_custom && bash scripts/precommit/run_pre_push.sh` → **passed**
- `bench --site test_site migrate` → **passed**
- `bench build --app ferum_custom` → **passed**
- `bench --site test_site execute ferum_custom.api.system_health.status` → **passed**

## 5) Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Adding `__init__.py` changes namespace semantics | If the same namespace existed from multiple sys.path entries, merging stops | Repo does not use multi-root namespaces; imports are all absolute and test/bench validations passed |
| Confusion around `ferum_custom.ferum_custom` persists | Developers may still assume it is “wrong” | Documented as Frappe module convention; recommend keeping module naming stable for now |
| Telegram bot entrypoint change | Bot may not start if Procfile/supervisor still uses old module path | Backward-compatible wrappers kept; update commands to `python -m ferum_custom.integrations.telegram_bot` |

## 6) Rollback Instructions

Git rollback (recommended):

1) `cd apps/ferum_custom`
2) `git revert <commit_sha>` (or `git restore .` if uncommitted)
3) From bench root:
   - `bench --site test_site migrate`
   - `bench build --app ferum_custom`

Note: removed directories like `ferum_custom/report/` and `ferum_custom/notifications/` were empty and untracked;
restoring them is unnecessary.
