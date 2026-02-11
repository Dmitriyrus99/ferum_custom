# Vault — настройка и cutover (AppRole/Token)

Цель: сделать Vault источником секретов для Ferum (Frappe + Telegram bot + FastAPI backend), без хардкода и без хранения секретов в БД/`.env`.

## 1) Что уже реализовано в коде

- Vault client с поддержкой **Token** и **AppRole** (`VAULT_ROLE_ID` + `VAULT_SECRET_ID`) и опционально `*_FILE`.
- Унифицированный settings слой: `frappe.conf` → env → Vault KV → `Ferum Custom Settings`.
- Операторские endpoints:
  - `ferum_custom.api.vault.health`
  - `ferum_custom.api.vault.sync_settings_to_vault` (idempotent, dry-run)
  - `ferum_custom.api.vault.clear_settings_secrets` (idempotent, manual cutover)
- Health-check: `ferum_custom.api.system_health.status` (не возвращает секреты).

## 2) Переменные окружения (bootstrap)

Минимум:

- `VAULT_ADDR` — например `https://vault.ferum.local:8200`
- `VAULT_MOUNT` — по умолчанию `secret`
- `VAULT_PATH` — путь KV, например `ferum/prod`

Аутентификация (один из вариантов):

- Token:
  - `VAULT_TOKEN` **или** `VAULT_TOKEN_FILE`
- AppRole:
  - `VAULT_ROLE_ID` + `VAULT_SECRET_ID`
  - или `VAULT_ROLE_ID_FILE` + `VAULT_SECRET_ID_FILE`

TLS (рекомендуется):

- `VAULT_CACERT=/path/to/ca.pem`
- опционально mTLS: `VAULT_CLIENT_CERT`, `VAULT_CLIENT_KEY`

Dev-only fallback (не рекомендовано в prod):

- `VAULT_SKIP_VERIFY=1`

## 3) Проверка доступности Vault

С ERP (не возвращает секреты):

- `bench --site <site> execute ferum_custom.api.vault.health`
- `bench --site <site> execute ferum_custom.api.system_health.status`

Важно: если Vault **sealed**, чтение KV будет падать. Разблокируй Vault (unseal) до cutover.

## 4) Миграция секретов в Vault (idempotent)

Dry-run (что будет записано):

- `bench --site <site> execute ferum_custom.api.vault.sync_settings_to_vault --kwargs "{'dry_run': 1, 'only_missing': 1}"`

Если Vault в состоянии **sealed** (unseal ещё не выполнен), режим `only_missing=1` не сможет прочитать текущие
значения из KV. В этом случае для предварительного просмотра списка ключей используй:

- `bench --site <site> execute ferum_custom.api.vault.sync_settings_to_vault --kwargs "{'dry_run': 1, 'only_missing': 0}"`

Применить:

- `bench --site <site> execute ferum_custom.api.vault.sync_settings_to_vault --kwargs "{'dry_run': 0, 'only_missing': 1}"`

Пояснение:

- `only_missing=1` не перезатирает существующие значения в Vault (безопаснее).
- Ключи в Vault пишутся теми же именами, что и env (например `FERUM_TELEGRAM_BOT_TOKEN`).

## 5) Cutover: убрать секреты из БД (manual, idempotent)

После того как убедился, что Vault KV содержит секреты:

Dry-run:

- `bench --site <site> execute ferum_custom.api.vault.clear_settings_secrets --kwargs "{'dry_run': 1, 'only_if_in_vault': 1}"`

Применить (очистит только те поля, для которых есть значения в Vault):

- `bench --site <site> execute ferum_custom.api.vault.clear_settings_secrets --kwargs "{'dry_run': 0, 'only_if_in_vault': 1}"`

Важно:

- Метод **не возвращает секреты**.
- По умолчанию `only_if_in_vault=1` защищает от случайной очистки БД при пустом/недоступном Vault.

## 6) Cutover: убрать секреты из env

После перехода на Vault рекомендуется удалить секретные значения из `.env`/env (оставить только `VAULT_*` bootstrap).

Проверка:

- `bench --site <site> execute ferum_custom.api.system_health.status`
- Runtime audit: `bench --site <site> execute ferum_custom.setup.audit.run --kwargs "{'write_report': 1}"`

## 7) Rollback (безопасный)

Самый простой откат:

1) Убрать/закомментировать `VAULT_*` переменные (или отключить их в process manager)
2) Вернуть секреты в `.env` или `Ferum Custom Settings`
3) Перезапустить процессы bench

Если секретов “на руках” нет — их можно прочитать из Vault (когда он доступен) и восстановить в `.env`.
