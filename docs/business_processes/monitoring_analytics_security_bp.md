# Мониторинг, аналитика и безопасность (AS‑IS: наблюдаемость + контроль конфигурации)

### Figure 7: Monitoring, Analytics & Security BPMN

![Monitoring, Analytics & Security BPMN](../images/monitoring_analytics_security_process.svg)

Документ описывает **реально доступные механизмы** мониторинга, диагностики, аналитики и security‑контроля в Ferum ERP (ERPNext/Frappe + `ferum_custom` + внешние сервисы).

См. также:

- runtime audit: `ferum_custom/setup/audit.py`
- health‑endpoint (Desk API): `ferum_custom/api/system_health.py`
- валидация security‑настроек: `ferum_custom/config/validation.py`
- Vault cutover/API: `ferum_custom/api/vault.py`, `ferum_custom/config/vault.py`

---

## 1) Логи и диагностика (операционный минимум)

### 1.1 Где смотреть логи (bench)

В bench‑контуре логи сервисов находятся в `logs/` и `sites/<site>/logs/`, типовые файлы:

- `logs/web.log`, `logs/web.error.log` — web‑процессы
- `logs/worker*.log`, `logs/worker*.error.log` — очереди/воркеры
- `logs/scheduler.log`, `logs/schedule.log`, `logs/schedule.error.log` — scheduler и задачи
- `logs/socketio.log`, `logs/node-socketio*.log` — websocket/socketio
- `logs/telegram-bot.log`, `logs/telegram-bot.error.log` — интеграция Telegram‑бота (если запущена как сервис)
- `logs/frappe.log`, `logs/database.log` — агрегированные логи Frappe/DB

Практика: при расследовании сначала фильтруем по времени и по ключевым словам (`Traceback`, `ValidationError`, `PermissionError`, `HttpError`).

### 1.2 Runtime audit (проверка целостности кастомизации)

В `ferum_custom` реализован runtime‑аудит, который помогает ловить “ломающие” регрессии:

- несуществующие модульные пути в hooks (ImportError)
- битые Query Report’ы при пустых фильтрах (типовая причина 500 в UI)
- Workflow’ы, ссылающиеся на несуществующие DocType
- регрессии Workspaces (“Объекты” ведут на legacy роуты/разные URL)
- health‑summary по интеграциям

Команда (пример):

- `bench --site test_site execute ferum_custom.setup.audit.run --kwargs "{'write_report': 1}"`

Результат сохраняется в `docs/audit/` (в репозитории приложения) и пригоден для PR‑ревью.

---

## 2) Health checks (интеграции и конфигурация)

### 2.1 Desk API: `system_health.status`

`ferum_custom.api.system_health.status` возвращает **non‑secret** статус конфигурации:

- наличие `wkhtmltopdf` (и версия)
- конфигурация Telegram‑бота (токен/режим/ERP API ключи)
- конфигурация FastAPI backend (base_url + auth_token)
- конфигурация Vault (auth‑режим + `/sys/health`)
- security validation (типовые misconfig: insecure JWT secret, VAULT_SKIP_VERIFY, права на `.env`)
- проверка Google Drive (корень/доступ/библиотеки)

Доступ: только роль `System Manager`.

### 2.2 FastAPI backend: `/api/v1/health`, `/metrics`

В репозитории есть FastAPI backend (`ferum_custom/integrations/fastapi_backend/*`), который поддерживает:

- `/api/v1/health` — healthcheck для оркестратора
- `/metrics` — Prometheus‑метрики (`prometheus_client`)
- Sentry SDK — если задан `SENTRY_DSN` (настройка через единый settings‑слой)

Важно: наличие кода ≠ факт включения в деплое. Включение/прокидка портов — задача инфраструктуры.

### 2.3 Telegram bot service: `/health`

Сервис бота (`ferum_custom/integrations/telegram_bot/main.py`) имеет health‑endpoint’ы (`/health`, `/tg-bot/health`) для простого мониторинга “процесс жив”.

---

## 3) Аналитика (AS‑IS)

Основной контур аналитики в текущей реализации — это:

- Query Report’ы (Frappe/ERPNext), в т.ч. с кастомными фильтрами
- доменные DocType (`Service Request`, `Invoice`, `ServiceAct`) как источник метрик

Критический контроль качества: **любой Query Report обязан отрабатывать при пустых фильтрах** (UI всегда шлёт `{}` при первом открытии). Это проверяется runtime audit (`check_module_query_reports`).

---

## 4) Безопасность (контроль доступа + конфигурация)

### 4.1 Контроль доступа в ERP (PQC/has_permission)

Для ключевых сущностей включены scripted‑проверки:

- permission query conditions: `Contract`, `File`, `Project Site`, `Service Logbook`, `Service Log Entry`
- has_permission: `File`, `Project Site`, часть портальных сущностей (Invoice/Sales Invoice/ServiceAct)

Реализация: `ferum_custom/security/*`.

### 4.2 Управление секретами

Секреты и интеграционные ключи читаются через единый typed‑settings слой:

- `frappe.conf` → `os.environ` → Vault KV → `Ferum Custom Settings` (fallback)

Это позволяет:

- не хранить секреты в репозитории
- постепенно “вырезать” секреты из DB в Vault
- проверять конфигурацию без раскрытия секретов (через health‑summary)

### 4.3 Security validation (авто‑предупреждения)

`ferum_custom/config/validation.py` реализует non‑secret проверки (пример):

- `.env` имеет слишком открытые права (рекомендация `chmod 600`)
- Vault использует HTTP или `VAULT_SKIP_VERIFY`
- JWT secret отсутствует или использует insecure default
- отсутствует токен Telegram‑бота

Эти проверки возвращаются через health‑endpoint и попадают в runtime audit.

---

## 5) Backup/Recovery (инфраструктурно, но с артефактами в репозитории)

В репозитории присутствует пример backup‑job (`backup-job.yml`), который запускает:

- `bench --site all backup`
- опционально: `restic backup sites` + политика retention

Реальный контур резервного копирования зависит от окружения (Docker Compose/k8s/VM), но минимальный критерий готовности:

- ежедневные бэкапы БД (и private files, если используются)
- тестовое восстановление в staging минимум 1 раз в квартал
