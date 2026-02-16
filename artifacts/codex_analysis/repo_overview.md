# Codex analysis — `ferum_custom` (repo overview)

Generated: 2026-02-16

Scope:

- Bench root: `/home/frappe/frappe-bench`
- App repo root: `/home/frappe/frappe-bench/apps/ferum_custom`

## Detected platform versions (from this environment)

| Component | Version | Status |
|---|---:|---|
| Python (bench env) | 3.12.3 | detected |
| Node.js | v24.11.0 | detected |
| npm | 11.6.4 | detected |
| Bench CLI | 5.27.0 | detected |
| Frappe | 15.92.0 | detected |
| ERPNext | 15.92.0 | detected |
| `ferum_custom` | 0.0.1 | detected |

Note: these are **environment facts** (not assumptions). Re-run `bench version` after upgrades.

## High-level repository structure (operational)

Primary app code and metadata:

- `ferum_custom/` — Frappe app Python package (`import ferum_custom`): hooks, services, APIs, integrations, security.
- `ferum_custom/ferum_custom/` — Frappe “Module” folder (`import ferum_custom.ferum_custom`): DocTypes, reports, module-scoped code.

Standalone service entrypoints (compatibility wrappers):

- `telegram_bot/` → wrapper for canonical bot under `ferum_custom/integrations/telegram_bot/`.
- `backend/` → wrapper for canonical FastAPI backend under `ferum_custom/integrations/fastapi_backend/`.

Docs and operator runbooks:

- `docs/` — architecture, runbooks, audit reports, business process docs.
- `docs/audit/` — non-secret audit artifacts (import maps, runtime audits, phase reports).
- `docs/runbooks/` — quality gates, runtime audit, telegram bot, vault, drive structure.

CI / quality:

- `.pre-commit-config.yaml` — ruff/format + prettier/eslint + pre-push compileall/tests.
- `.github/workflows/` — CI, linters/security (Semgrep), optional deploy workflow.

## “Points of truth” for customization in this app

Frappe integration map:

- `ferum_custom/hooks.py` — **active hook targets** (doc events, scheduler, permission hooks, overrides).

Schema/data evolution:

- `ferum_custom/patches.txt` + `ferum_custom/patches/**` — idempotent migrations, UI/Workspace fixes, legacy transitions.

DocType definitions:

- `ferum_custom/ferum_custom/doctype/**/<doctype>.json` — DocType meta (fields/permissions/autoname).
- `ferum_custom/ferum_custom/doctype/**/<doctype>.py` — controllers (server-side invariants).

Operational checks:

- `ferum_custom/setup/audit.py` — runtime audit via `bench execute` (imports, doctypes, query reports, workflows, workspaces, system health).
- `ferum_custom/api/system_health.py` — consolidated health payload (Drive / Telegram / FastAPI / Vault / config validation).

External integrations:

- Telegram bot: `ferum_custom/integrations/telegram_bot/` (aiogram webhook/polling, calls ERP via token auth).
- Google Drive: `ferum_custom/api/project_drive.py` + `ferum_custom/integrations/google_drive_folders.py`.
- Vault: `ferum_custom/config/vault.py` + `ferum_custom/config/settings.py` + `ferum_custom/api/vault.py`.

## Where to look next (fast navigation)

- Full repo tree (depth=4): `apps/ferum_custom/artifacts/codex_analysis/repo_tree.txt`
- Hooks map (what actually runs): `apps/ferum_custom/artifacts/codex_analysis/hooks_map.md`
- DocType inventory: `apps/ferum_custom/artifacts/codex_analysis/doctype_inventory.md`
- Patches inventory: `apps/ferum_custom/artifacts/codex_analysis/patches_inventory.md`
- CI/CD map + commands: `apps/ferum_custom/artifacts/codex_analysis/ci_cd_map.md`
- Risks + recommendations: `apps/ferum_custom/artifacts/codex_analysis/risks_and_findings.md`
