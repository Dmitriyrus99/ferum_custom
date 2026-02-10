# Управление заявками на обслуживание (Service Request)

Дата: 2026‑02‑10  
Контур: ERPNext/Frappe v15 + `ferum_custom`.

Цель процесса: принимать обращения по объектам, назначать исполнителя, контролировать SLA и закрывать заявки только при наличии отчёта о работах.

## Участники

- **Client** — создаёт/отслеживает заявки в рамках своих проектов (через бот/портал при наличии доступа).
- **Office Manager / Project Manager** — регистрирует обращения (телефон/почта), назначает инженера, контролирует сроки.
- **Engineer** — выполняет работы, прикладывает доказательства (фото/файлы), подготавливает отчёт.
- **System Manager** — поддержка интеграций и прав.

## AS‑IS: входящие каналы

1) **ERPNext Desk**
   - ручное создание `Service Request` офисом/PM
2) **Telegram‑бот**
   - создание заявки через Telegram → ERP API (`ferum_custom/api/telegram_bot.py`)
3) **Регламент (scheduler)**
   - ежедневная генерация заявок по графику (`ferum_custom/services/service_schedule.py`)
   - текущая реализация использует legacy `service_object` (требует модернизации под `project_site`)

## Модель данных заявки (ключевые поля)

- привязка к объекту:
  - **новый контур:** `erp_project` (Project) + `project_site` (Project Site, truth)
  - **legacy:** `service_object` (Service Object)
- управление:
  - `status` (Open → In Progress → Completed → Closed / Cancelled)
  - `assigned_to`, `priority`, `type`, `description`
- фиксация времени/источника:
  - `registered_datetime` (время регистрации в ERP)
  - `reported_datetime` (время обращения; может отличаться при внешних источниках)
  - `source_channel`, `source_reference`, `source_evidence_file`
- SLA:
  - `sla_deadline` вычисляется от `reported_datetime` (если заполнено), иначе от `registered_datetime/creation`

Серверная логика: `ferum_custom/ferum_custom/doctype/service_request/service_request.py`.

## Правила и проверки (инварианты)

- нельзя перевести в `In Progress` без `assigned_to`
- нельзя перевести в `Completed` без `linked_report` (если поле существует)
- для внешних источников (`Email/Phone/EIS/Other`) при отличии `reported_datetime` от `registered_datetime` требуется:
  - `source_reference` **или**
  - `source_evidence_file`

## Уведомления

События:

- `Service Request.after_insert` — уведомление о новой заявке
- `Service Request.on_update` — уведомление о смене статуса

Реализация: `ferum_custom/notifications.py` (email + telegram best‑effort).

## Доказательная база (фото/вложения)

AS‑IS для Telegram‑канала:

- вложения к заявке и “обследование” загружаются в Google Drive
- ссылки на папки/файлы сохраняются в ERP (комментарии/поля checklist)

API: `ferum_custom/api/telegram_bot.py`  
Drive: `ferum_custom/api/project_drive.py`
