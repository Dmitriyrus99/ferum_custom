# Codex analysis — risks & findings (P0–P3)

Generated: 2026-02-16

This report is based on **repository facts** (hooks/doctypes/patches/CI) plus a small set of **current environment
observations** (bench/audit/health). No secrets are included.

## Executive summary

`ferum_custom` is closer to a “product-grade” ERPNext app than a one-off customization:

- Centralized hook map (`hooks.py`) + extensive idempotent patch set (`patches.txt`).
- Quality gates: pre-commit + CI with bench install/migrate/run-tests.
- Security posture: Semgrep (Frappe rules) + permission hooks + runtime audit + Vault-oriented settings layer.

Main operational risks are around **external dependencies** (Vault/Drive/Telegram) and **long-lived legacy model
coexistence** (Service Project/Object + new Project/Site truth model).

## P0 (breaks production / security)

### P0.1 Secret handling regressions (preventive)

Risk:

- Any accidental logging/printing of tokens (Telegram bot token, ERP API key/secret, Vault AppRole secret_id, Google
  SA JSON) is catastrophic and hard to detect after the fact.

Mitigations present:

- Unified settings layer (`ferum_custom/config/settings.py`) supports Vault and avoids scattering env access.
- Security validation exists (`ferum_custom/config/validation.py`) and is surfaced via `system_health`.
- Runbooks explicitly warn about token leakage and rotation.

Recommendation:

- Keep “no secrets in logs” as a non-negotiable rule. Add regression tests for redaction if any debug utilities exist.

## P1 (high risk downtime / data exposure)

### P1.1 Vault configured but sealed (environment observation)

Observed:

- Runtime audit flags `vault.sealed` when Vault is configured but not unsealed (this is intentional guardrail).

Impact:

- Vault KV reads fail; system falls back to env/DB settings, but operators may assume Vault cutover already happened.

Action:

- Unseal Vault, run sync + cutover per `docs/runbooks/vault.md`, restart processes, re-run runtime audit.

### P1.2 Permission hooks correctness (data isolation)

Risk:

- `permission_query_conditions` and `has_permission` are security-critical. A single incorrect SQL condition can leak
  documents across projects/clients.

Mitigations present:

- Permission checks are centralized under `ferum_custom/security/*`.
- Runtime audit validates hook imports and key report failure modes.
- CI includes app tests (`bench run-tests --app ferum_custom`) and Semgrep rules.

Recommendation:

- Add/extend tests for `project_access.projects_for_user()` boundaries and “Client sees only allowed doc types” for
  File attachments.

### P1.3 External API latency in request path (Drive / Telegram)

Risk:

- Drive folder creation/upload and outbound Telegram calls are IO-heavy and can slow down web requests if executed
  synchronously.

Mitigations present:

- Drive operations are behind explicit admin actions (`ensure_drive_folders`) and have best-effort error handling.
- Notifications have fallback behavior (FastAPI → direct Telegram send).

Recommendation:

- For high-volume production use, move heavy external calls to background jobs (RQ queues) and make API methods
  idempotent “enqueue only”.

## P2 (tech debt / maintainability)

### P2.1 Hybrid package layout (`ferum_custom` + `ferum_custom.ferum_custom`)

Observed:

- Outer app package contains runtime logic; inner module folder contains DocTypes/reports/tests.
- Compatibility shims already exist (e.g. query report override wrapper).

Risk:

- Import drift and developer confusion (“куда класть код”, “почему два namespace”).

Mitigation:

- Keep inner folder focused on DocTypes/Reports/fixtures and canonicalize runtime entrypoints under outer package.

References:

- `docs/package_refactor_report.md`

### P2.2 Legacy model coexistence (Service Project / Service Object)

Observed:

- Legacy doctypes are intentionally made read-only / hidden for non-admin users.

Risk:

- “Accidental revival” of legacy flows through UI shortcuts or old reports can reintroduce inconsistent data.

Mitigation:

- Keep legacy doctypes read-only + keep reports/workspaces pointing to the truth model (`Project` + `Project Site`).
- Maintain migration patches and add runtime audit checks for workspace shortcut consistency.

### P2.3 Test layout expectations

Observed:

- Repo-level `pytest` is focused on `backend/tests` (configured in `pyproject.toml`).
- Frappe integration tests live under module path and are executed via `bench run-tests`.

Risk:

- Developers may run `pytest` on the wrong paths and assume “no tests exist”.

Mitigation:

- Document “which tests run where” and provide a single “verification” command list (already partly covered in runbooks).

### P2.4 Historical infra errors in bench logs (environment observation)

Observed in `frappe-bench/logs/` (older timestamps):

- `schedule.error.log`: `OSError: [Errno 24] Too many open files: ./apps.txt`
- worker logs: Redis connection resets (likely during restarts)
- telegram bot: occasional `TelegramNetworkError: Request timeout error`

Risk:

- Ulimit / FD exhaustion or unstable DNS/network can intermittently break scheduler/bot.

Mitigation:

- Confirm current `ulimit -n` and supervisor/systemd limits.
- Ensure stable DNS resolver inside container/VM (bot has `_dns_preflight()` and forces IPv4; still check infra).

## P3 (nice-to-have improvements)

### P3.1 Automate artifact generation (repeatable “audit pack”)

Idea:

- Add a small script to regenerate `artifacts/codex_analysis/*` and validate it in CI (no secrets).

### P3.2 Expand runtime audit checks

Ideas:

- Validate every patch module listed in `patches.txt` exists on disk.
- Check for “dangling” Workspace shortcuts (multiple URLs for “Объекты”).
- Add a lightweight permission smoke (create sample docs in tests / check list access).

## Next PR-sized tasks (5–8 concrete items)

1) **Artifacts generator script**
   - Goal: re-generate `artifacts/codex_analysis/*` deterministically.
   - Files: `scripts/codex_analysis/generate.py` + docs.
   - DoD: script runs without bench/DB; CI job can run it; no secrets.

2) **Patch list integrity check**
   - Goal: fail fast if `patches.txt` references missing modules.
   - Files: `ferum_custom/setup/audit.py` (new check) + tests.
   - DoD: runtime audit reports `patches.missing_module` as P0 when applicable.

3) **Permission regression tests (Client + File)**
   - Goal: prove clients cannot access disallowed File doc types.
   - Files: `ferum_custom/security/file_permissions.py` tests under Frappe test suite.
   - DoD: `bench run-tests --app ferum_custom` covers both allow/deny paths.

4) **Drive operations as background jobs**
   - Goal: avoid long request latency for Drive folder/file operations.
   - Files: `ferum_custom/api/project_drive.py`, new `ferum_custom/utils/background_jobs/*`.
   - DoD: API enqueues jobs; job execution idempotent; audit/health unchanged.

5) **Telegram bot reliability hardening**
   - Goal: reduce “silent no response” cases.
   - Files: `ferum_custom/integrations/telegram_bot/*`.
   - DoD: add retry/backoff around outbound sends; log structured error category; keep webhook processing alive.

6) **Version-16 readiness spike (non-breaking)**
   - Goal: create a documented checklist and a CI matrix job for Frappe/ERPNext v16 (optional).
   - Files: `.github/workflows/ci.yml`, `docs/runbooks/product_readiness_checklist.md`.
   - DoD: optional job runs on demand; no production behavior changes.
