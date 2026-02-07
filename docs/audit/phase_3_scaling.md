# PHASE 3 — Scaling (Contract Tests, Load Scenarios, Scalability Report)

Date: 2026-02-05

## 1) Scope & Goals

Phase 3 adds “scale-readiness” tooling and guardrails:

- Contract tests for key integration client behavior (Telegram bot → ERP API).
- A lightweight, reproducible HTTP load runner for basic latency/error profiling.
- A scalability report: bottlenecks, risks, and concrete next steps for 3–5 years growth.

Constraints honored:

- No secrets in code/output.
- No breaking changes to runtime behavior.
- Tests added and executed.

## 2) Dependency & Risk Map (Phase 3)

### Dependency map

| Item | Depends on | Notes |
|---|---|---|
| Contract tests (`backend/tests/test_contract_frappe_api.py`) | `ferum_custom.integrations.telegram_bot.frappe.FrappeAPI`, `httpx` | Uses `httpx.MockTransport` (offline, deterministic). Backward-compat import path is tested too. |
| Load runner (`scripts/scaling/http_load.py`) | `httpx` | Pure GET load; supports `Host` header for multi-tenant sites. |

### Risk map

| Risk | Impact | Mitigation in this phase |
|---|---|---|
| Accidental overload of production | degraded ERP performance | conservative defaults, explicit CLI flags for concurrency/duration, docs clarify intended usage |
| Secrets printed in load output | secret disclosure | script prints only aggregate metrics; auth values never printed |
| Wrong site routing (multi-tenant) | misleading perf data | `--host-header` support; docs include examples |

## 3) Patch Set (Code Changes)

- Contract tests:
  - `backend/tests/test_contract_frappe_api.py`
- Load tooling:
  - `scripts/scaling/http_load.py`

## 4) Contract Tests (Integration Interfaces)

Added tests for Telegram bot’s ERP API client contract:

- `backend/tests/test_contract_frappe_api.py`
  - verifies URL construction (`/api/resource/...`, encoding of doctypes with spaces)
  - verifies auth header format (`Authorization: token <key>:<secret>`)
  - verifies error extraction and exception behavior on non-2xx responses

Why this matters:

- Telegram bot stability depends on a consistent ERP API contract. These tests catch accidental regressions
  during refactors and dependency upgrades.

## 5) Load Scenarios (Reproducible)

Added a simple load runner (async HTTP client, concurrency, summary stats):

- `scripts/scaling/http_load.py`

Example (local bench web):

- `./apps/ferum_custom/scripts/scaling/http_load.py --base-url http://127.0.0.1:8000 --host-header test_site --endpoint /api/method/ping --duration-seconds 15 --concurrency 25`

If authentication is required for the chosen endpoint:

- `./apps/ferum_custom/scripts/scaling/http_load.py --base-url https://<site> --api-key <KEY> --api-secret <SECRET> --endpoint /api/method/frappe.ping`

The script prints a JSON report:

- request totals, status code distribution
- latency min/p50/p95/p99/max (ms)

Sample baseline run (dev bench, `ping`, 10s, concurrency 25):

- `total_requests`: 1399
- `status_codes`: 200=1399
- latency (ms): p50≈149, p95≈209, p99≈1027, max≈1055

Note: if the site is in maintenance mode you will get `503 Session Stopped`; disable `maintenance_mode` to run.

## 6) Scalability Analysis (Current Constraints)

### Primary bottlenecks (most likely)

- **MariaDB**: slow reports/filters, missing indexes for high-cardinality fields, large joins.
- **Redis queue**: worker throughput, long-running jobs blocking queues, retry storms.
- **External APIs** (Google Drive, Vault, Telegram): latency + quota, cascading failures if called synchronously.

### Hot paths to monitor

- Service Request creation/update (workflow + notifications)
- Drive folder creation + file upload (API calls, retries, quota errors)
- Report execution (SQL time, rows scanned, missing filters)
- Bot webhook handler and outbound Telegram requests (DNS/network issues, rate limits)

## 7) Recommendations (3–5 year horizon)

### Architecture

- Keep ERPNext/Frappe as the authoritative domain model; push slow IO (Drive/Vault/Telegram) to background jobs
  where possible.
- Prefer idempotent integration calls + retries with backoff, and cache results (Vault KV already cached).

### Reliability

- Define SLOs:
  - `p95 < 500ms` for common UI actions
  - `p99 < 2s` for API endpoints
- Add alerting for:
  - worker error rates
  - queue length + job age
  - DB slow queries

### Performance

- Ensure reports are safe with empty filters and use indexed columns.
- For heavy reporting: add dedicated summary tables/materialized views if needed (but only after measurement).

## 8) Validation Executed

- `pytest` (app repo) — contract tests + existing unit tests passed.
- `pre-commit run --all-files` — passed.
