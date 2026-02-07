# Ferum / ERPNext — чек‑лист доводки до продакшена

Документ фиксирует список задач/проверок, чтобы довести текущую систему до состояния «готово к эксплуатации» (надёжность, безопасность, повторяемость деплоя).

## Важно: текущие блокеры среды

Если бот/интеграции «вдруг перестали отвечать», в первую очередь проверьте инфраструктуру:

1. **DNS в контейнере/VM**: если в `/etc/resolv.conf` указан `nameserver 127.0.0.53`, а `systemd-resolved` не работает внутри контейнера — резолвинг доменов сломан (Telegram/Vault/Google API недоступны).
2. **Запрещены socket/syscalls** (seccomp/no-new-privileges): тогда падают любые подключения (MySQL/HTTP). Это не лечится кодом приложения — нужно править политику контейнера/хоста.

## 0) Термины и области

- **bench**: `/home/frappe/frappe-bench`
- **app**: `apps/ferum_custom/ferum_custom` (Frappe app `ferum_custom`)
- **telegram bot**: `apps/ferum_custom/ferum_custom/integrations/telegram_bot` (aiogram бот; старый путь `apps/ferum_custom/telegram_bot` — wrapper)
- **Drive**: интеграция с Google Drive через service account
- **Vault**: Hashicorp Vault (KV secrets), источник конфигурации/секретов

## 1) Инфраструктура и ОС

1. Установить/проверить `wkhtmltopdf 0.12.x (patched qt)` на уровне ОС.
   - Проверка: `wkhtmltopdf --version`
2. Проверить, что сервисы bench стартуют и переживают рестарт:
   - `redis_cache`, `redis_queue`, `web`, `socketio`, `schedule`, `worker-*`, `telegram-bot`.
3. Проверить DNS/сетевой доступ:
   - сервер должен видеть `api.telegram.org`, `drive.google.com`/Google APIs, `vault.<domain>`.

## 2) Конфигурация и секреты (единый источник истины)

Цель: **Vault → генерация `.env`/`site_config.json` → процессы bench**.

1. Привести `.env.example` к виду шаблона (без секретов), а реальные значения хранить:
   - в Vault (предпочтительно) или
   - в защищённом секрет‑хранилище CI/CD.
2. Определить структуру в Vault (KV v2 рекомендуется):
   - `VAULT_MOUNT` (например `secret`)
   - `VAULT_PATH` (например `ferum/erpnext/<env>/bench`)
3. Выбрать метод аутентификации:
   - `VAULT_TOKEN` (временно/для ручных проверок) или `VAULT_TOKEN_FILE` (файл с токеном) или
   - `AppRole` (`VAULT_ROLE_ID` + `VAULT_SECRET_ID`, либо файлы `VAULT_ROLE_ID_FILE` + `VAULT_SECRET_ID_FILE`) для CI/прод.
4. Включить TLS‑проверку:
   - `VAULT_CACERT` (CA), опционально mTLS (`VAULT_CLIENT_CERT`/`VAULT_CLIENT_KEY`).
5. Генерация `.env` из Vault (скрипт в репозитории):
   - см. `apps/ferum_custom/scripts/render_env_from_vault.py`.
6. Определить политику для значений «констант»:
   - **не хранить** в коде/репозитории,
   - хранить в Vault → рендерить в `.env` → `bench restart`.

## 3) Telegram‑бот (стабильный запуск и диагностика)

1. Конфигурация в `.env`:
   - `FERUM_TELEGRAM_BOT_TOKEN`
   - `FERUM_FRAPPE_BASE_URL`, `FERUM_FRAPPE_API_KEY`, `FERUM_FRAPPE_API_SECRET`
   - режим: `FERUM_TELEGRAM_MODE=polling|webhook`
2. Старт процесса:
   - `Procfile` должен содержать `telegram-bot: ...`
3. Диагностика:
   - лог: `logs/telegram-bot.log` и `logs/telegram-bot.error.log`
   - добавить healthcheck/самопроверку (getMe / ping до ERP API).
4. Инфраструктура webhook (если используется `mode=webhook`):
   - публичный URL должен быть доступен Telegram,
   - обратный прокси должен прокидывать на `:8080/tg-bot/webhook`,
   - DNS внутри контейнера должен резолвить `api.telegram.org` (бот не сможет отвечать без исходящих запросов).

## 4) Google Drive (документы проектов/контрактов)

1. Проверка конфигурации:
   - service account json доступен в `sites/<site>/private/keys/`
   - задан root folder id (в `.env` или `site_config.json`)
2. Структура папок должна быть детерминированной и на русском (версия `ru_v1`):
   - создаётся `ferum_custom.api.project_drive.ensure_drive_folders`
   - массовая миграция: `ensure_drive_folders_bulk`
3. Метаданные:
   - `00_МЕТА/project.json` и `02_ОБЪЕКТЫ/<object>/00_МЕТА/object.json`
4. UI:
   - загрузка/листинг документов в Project/Contract
   - обязательные поля: наименование + тип
5. Права:
   - загрузка: Admin / Project Manager / Office Manager
   - просмотр: Admin / PM / Engineer (в рамках доступа) / Client (ограниченные типы)

## 5) Целостность DocType/пачей/воркспейсов

1. Файловая целостность doctypes:
   - в `apps/ferum_custom/ferum_custom/ferum_custom/doctype/<dt>/` должны быть `<dt>.json`, `<dt>.py`, `__init__.py`
2. Отсутствующие json/py не должны приводить к `FileNotFoundError` при открытии DocType.
3. Workspaces:
   - единые shortcuts «Объекты» (везде один и тот же смысл и один и тот же target)
   - запретить ситуацию, когда «Объекты» ведут на ERPNext `Asset`
4. Отчёты:
   - Query Report должен быть устойчив к пустым фильтрам (`KeyError: 'project'` и т.п.)
5. Пользователи/Module Profile:
   - привести профили/роли к ожидаемой модели доступа (PM/Engineer/Client),
   - проверить, что пользователи видят только нужные модули и имеют доступ только к своим проектам.

## 6) Функциональные smoke‑проверки (после migrate)

После `bench --site <site> migrate` + `bench --site <site> clear-cache` + `bench restart`:

1. Project: открытие формы, workflow, создание/обновление.
2. Документы: загрузка/листинг/фильтры + права (PM/Engineer/Client).
3. Drive: создание папок + корректный `drive_folder_url`.
4. Telegram:
   - бот отвечает на `/start`, `/help`
   - команды `/requests`, `/new_request ...` работают для привязанных пользователей.
5. Отчёты:
   - `Invoices by Project`, `Service Requests by Project`, `Project Profitability` (без 500/417).
6. Инвойсы:
   - Sales Invoice / Purchase Invoice формы отображают поля и сохраняются.

## 7) Набор артефактов «готово к прод»

1. Скрипт генерации `.env` из Vault + runbook.
2. Healthcheck интеграций (Drive/Telegram/Vault/fastapi).
3. Контроль миграций/патчей без ручных правок БД.
4. Минимальный QA‑протокол (команды + ожидаемый результат).
5. Runbook по восстановлению после ошибок:
   - как быстро проверить DNS, доступность Vault/Telegram/Drive,
   - как безопасно перегенерировать `.env` и перезапустить bench,
   - как сделать rollback (откат патча/скрипта) при проблемах.
