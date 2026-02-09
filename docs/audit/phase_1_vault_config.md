# PHASE 1 — Vault & Config (Implementation Report)

Date: 2026-02-05

## 1) Scope & Goals

Implemented Phase 1 deliverables:

- Vault **AppRole/Token** KV provider (runtime) with safe caching.
- Unified, typed settings layer for Frappe + Telegram bot + FastAPI backend.
- Safe migration path for moving secrets from DB/env into Vault KV (idempotent).
- Security/config validation surfaced via `system_health`.

Constraints honored:

- Backward compatible (existing env + `Ferum Custom Settings` still work).
- No hardcoded secrets added.
- All migrations/actions are idempotent.
- Tests added and validation executed.

## 2) Current Config Landscape (Scan Summary)

Primary config sources observed in codebase:

- `frappe.conf` (site/common config)
- process env vars (supervisor/docker/systemd)
- bench `.env` (loaded ad-hoc in multiple modules before this phase)
- `Ferum Custom Settings` single DocType (contains encrypted Password fields + non-secret fields)

Key secret-bearing fields in `Ferum Custom Settings`:

- `telegram_bot_token` (Password)
- `telegram_webhook_secret` (Password)
- `jwt_secret` (Password)
- Google service account JSON attachment (Attach)

## 3) Dependency Map (What Needs What)

| Component | Purpose | Required/Typical keys (aliases supported) |
|---|---|---|
| Vault client | source of truth for secrets | `VAULT_ADDR`, `VAULT_MOUNT`, `VAULT_PATH`, auth: `VAULT_TOKEN` (**or** `VAULT_TOKEN_FILE`) **or** `VAULT_ROLE_ID`+`VAULT_SECRET_ID` (**or** `VAULT_ROLE_ID_FILE`+`VAULT_SECRET_ID_FILE`), TLS: `VAULT_CACERT`/`VAULT_CLIENT_CERT`/`VAULT_CLIENT_KEY` |
| Frappe app | notifications, integrations | `FERUM_TELEGRAM_BOT_TOKEN`, `FERUM_FASTAPI_BASE_URL`, `FERUM_FASTAPI_AUTH_TOKEN`, Drive keys, etc. |
| Telegram bot | reply/send commands | `FERUM_TELEGRAM_BOT_TOKEN`, webhook keys (`FERUM_TELEGRAM_WEBHOOK_URL`…), ERP API keys |
| FastAPI backend | portal/integration API | `FERUM_JWT_SECRET` (alias `SECRET_KEY`), `FERUM_FRAPPE_BASE_URL` (alias `ERP_API_URL`), `FERUM_FRAPPE_API_KEY`/`FERUM_FRAPPE_API_SECRET`, `REDIS_URL`, `SENTRY_DSN` |
| Google Drive | folder + upload | `FERUM_GOOGLE_DRIVE_ROOT_FOLDER_ID`, service account key **file** or **JSON** |

Design rule: Vault KV should store keys using the same names as env keys (e.g. `FERUM_TELEGRAM_BOT_TOKEN`), so all components can resolve them identically.

## 4) Risk Map (Key Risks + Mitigations)

| Risk | Impact | Mitigation implemented |
|---|---|---|
| Vault sealed/unreachable | startup latency, missing secrets | Vault reads are cached and failure-backed-off (avoids hammering); `system_health` exposes Vault health |
| `VAULT_SKIP_VERIFY=1` | MITM risk | surfaced as P1 issue in validation output |
| Secrets left in DB/env | auditability + drift | migration method writes to Vault; runtime prefers `frappe.conf/env` first for backward compatibility |
| Drive SA JSON managed manually | operational errors | Drive integration now accepts **JSON content** via config and materializes a keyfile under `sites/<site>/private/keys/` |

## 5) Patch Set (Code Changes)

### New unified settings + Vault runtime

- `ferum_custom/config/dotenv.py` — shared dotenv loader (best effort, no overrides).
- `ferum_custom/config/vault.py` — Vault KV client:
  - Token or AppRole auth
  - KV v2 with v1 fallback
  - in-memory caching + token TTL
- `ferum_custom/config/settings.py` — provider chain:
  - `frappe.conf` → env → Vault → `Ferum Custom Settings`
  - typed helpers (`get_int`, `get_bool`, `get_int_set`)
  - failure backoff for Vault reads
- `ferum_custom/config/validation.py` — non-secret security validation summary

### Integration adoption

- `ferum_custom/api/system_health.py` — uses unified settings, adds Vault `/sys/health` summary + security validation.
- `ferum_custom/notifications.py` — uses unified settings for FastAPI + Telegram config.
- `ferum_custom/api/telegram_bot.py` — uses unified settings for bot token (Vault becomes valid source).
- `ferum_custom/integrations/google_drive_folders.py` — uses unified settings and supports JSON content for SA key (writes keyfile safely).
- `ferum_custom/integrations/telegram_bot/settings.py` — uses unified settings layer + Vault support (old `telegram_bot/...` kept as wrapper).
- `ferum_custom/integrations/fastapi_backend/config.py` — uses unified settings layer + Vault support (keeps backward-compatible defaults; `backend/...` kept as wrapper).

### Migration endpoint (idempotent)

- `ferum_custom/api/vault.py`:
  - `health()` — operator-safe Vault status.
  - `sync_settings_to_vault(dry_run=1, only_missing=1)` — writes selected secrets into Vault KV without returning values.

## 6) Tests & Validation

Added unit tests:

- `backend/tests/test_settings_vault.py` — settings precedence + Vault client read/write merge behavior.

Validation executed:

- `pytest` (app repo) — all tests passed.
- `pre-commit run --all-files` — passed (ruff/format/eslint/prettier hooks clean).

## 7) Operator Runbook (How to Enable Vault)

1) Configure Vault bootstrap variables (env or bench `.env`):

- `VAULT_ADDR=https://...`
- `VAULT_MOUNT=secret` (or your mount)
- `VAULT_PATH=<kv/path>`
- Auth:
  - `VAULT_TOKEN=...` **or**
  - `VAULT_ROLE_ID=...` + `VAULT_SECRET_ID=...`
- TLS (recommended):
  - `VAULT_CACERT=/path/to/ca.pem` (preferred) **or** client certs

2) Sync existing values into Vault (dry run first):

- `bench --site <site> execute ferum_custom.api.vault.sync_settings_to_vault --kwargs \"{'dry_run': 1, 'only_missing': 1}\"`
- Then apply:
  - `bench --site <site> execute ferum_custom.api.vault.sync_settings_to_vault --kwargs \"{'dry_run': 0, 'only_missing': 1}\"`

Optional cutover (remove secrets from DB after verifying Vault has them):

- dry-run:
  - `bench --site <site> execute ferum_custom.api.vault.clear_settings_secrets --kwargs \"{'dry_run': 1, 'only_if_in_vault': 1}\"`
- apply:
  - `bench --site <site> execute ferum_custom.api.vault.clear_settings_secrets --kwargs \"{'dry_run': 0, 'only_if_in_vault': 1}\"`

3) Verify:

- `bench --site <site> execute ferum_custom.api.system_health.status`
- (optional) `bench --site <site> execute ferum_custom.api.vault.health`

Rollback:

- Unset `VAULT_*` / `FERUM_VAULT_*` bootstrap variables and restart processes. System falls back to env/DB settings.
