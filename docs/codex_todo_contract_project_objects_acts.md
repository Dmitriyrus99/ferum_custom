# TODO (Codex CLI): Contract → Project → Objects → Acts → Client access

Этот документ — “истина” по целевой модели и задачам для разработки в `apps/ferum_custom`.
Используется Codex CLI как рабочее ТЗ/чеклист.

## A) Data Model: DocTypes + поля

### A1) Contract (стандартный DocType) — Custom Fields

Создать Custom Fields (DocType: `Contract`).

**Обязательные:**
- `company` (Link, Options=`Company`) `reqd=1`
- `document_mode` (Select) options:
  - `UPD_ONLY`
  - `ACT_PLUS_INVOICE`
- `submission_channel` (Select) options:
  - `EIS`
  - `PIK`
  - `MAIL`
  - `EDO`
  - `OTHER`
- `acts_deadline_day` (Int) min 1 max 31
- `payment_terms_template` (Link, Options=`Payment Terms Template`)
- `project_manager` (Link, Options=`User`)
- `account_manager` (Link, Options=`User`)
- `is_portal_visible` (Check) default=1

**Дополнительно:**
- `contract_code` (Data)
- `contract_value` (Currency) (если стандартного поля “value” нет/не подходит)
- `document_folder_url` (URL) (если URL fieldtype недоступен — Data)

**Нормализация party (важно):**
- Валидация: `party_type == "Customer"` и `party_name` существует как `Customer`.
- Практично: если пользователь выбирает `party_name`, автозаполнять `party_type="Customer"` и блокировать другие значения.

### A2) Project (стандартный DocType) — 1:1 к Contract

Custom Field (DocType: `Project`):
- `contract` (Link, Options=`Contract`) + уникальность enforce’ится кодом

Валидации:
- `Contract` обязателен для “наших” проектов
- Нельзя создать второй `Project` на тот же `Contract`

Автосинк полей из `Contract` (на save Contract):
- `customer` (если используете Customer в Project — зависит от конфигурации)
- `company`
- `project_manager`

### A3) Service Object (кастомный) — “паспорт”

DocType: `ServiceObject` (если уже есть — довести).

Поля:
- `customer` (Link Customer) `reqd`
- `address` (Link Address)
- `address_text` (Small Text) (резерв)
- `coordinates` (Geolocation) (опционально)
- child table `object_contacts` (опционально):
  - `name/role/phone/email`

### A4) Contract ↔ Service Object (N:M) — ключевой DocType

DocType: `ContractServiceObject`

Поля:
- `contract` (Link Contract) `reqd`
- `service_object` (Link ServiceObject) `reqd`
- `status` (Select) options: `Active\nInactive` default `Active`
- `service_frequency` (Select) (например: `Monthly\nQuarterly\nSemiannual\nAnnual\nCustom`)
- `sla_response_hours` (Int)
- `sla_fix_hours` (Int)
- `access_windows` (Small Text)
- `is_billable` (Check) default=1

Ограничения:
- Unique pair `(contract, service_object)` (минимум через `validate()`, желательно и индексом позже)

Валидация:
- `service_object.customer == contract.party_name` (при `party_type=Customer`)

## B) Актирование: Schedule + Service Act + Invoice

### B1) Act Schedule (кастомный)

DocType: `ActSchedule`

Поля:
- `contract` (Link Contract) `reqd`
- `project` (Link Project) `reqd` (авто из Contract→Project)
- `period_from` (Date) `reqd`
- `period_to` (Date) `reqd`
- `planned_amount` (Currency)
- `planned_submit_date` (Date) (авто)
- `submission_channel` (Select) (snapshot, копия из Contract)
- `document_mode` (Select) (snapshot, копия из Contract)
- `status` (Select) options:
  - `Planned`
  - `Prepared`
  - `Submitted`
  - `Signed`
  - `Invoiced`
  - `Paid`
  - `Skipped`
  default `Planned`

Правила:
- `period_to >= period_from`
- `planned_submit_date` вычислять как: “месяц `period_to` + `acts_deadline_day`” (с безопасной коррекцией на конец месяца)

### B2) Service Act (кастомный)

DocType: `ServiceAct`

Поля:
- `schedule` (Link ActSchedule) (может быть reqd, если всегда из плана)
- `contract` (Link Contract) `reqd`
- `project` (Link Project) `reqd`
- `customer` (Link Customer) (fetch from contract.party_name)
- `period_from` (Date) `reqd`
- `period_to` (Date) `reqd`
- `amount` (Currency) `reqd`
- `objects` (Table) — строки выбора из `ContractServiceObject`:
  - `contract_service_object` (Link ContractServiceObject)
  - (опционально) notes
- `files` (Attach/таблица вложений — по принятому паттерну)
- `status` (Select/Workflow)
- `sales_invoice` (Link Sales Invoice)
- `sign_date` (Date)
- `document_number` (Data)

Workflow:
- `Prepared → Submitted → Signed (+ Cancelled)`

Связь со schedule:
- при создании `ServiceAct` из `ActSchedule`: копировать snapshot поля и сумму/период.

### B3) Генерация Sales Invoice (AR живёт в Sales Invoice)

Логика:

`UPD_ONLY` (Компания “Ферум”):
- on `ServiceAct.status -> Signed`:
  - если `sales_invoice` пуст → создать `Sales Invoice` автоматически (минимум 1 item “Services by Contract …”)
  - записать ссылку обратно в `service_act.sales_invoice`
  - обновить `schedule.status` (`Signed`/`Invoiced`)

`ACT_PLUS_INVOICE` (Компания “Ферум СБ”):
- кнопка “Create Sales Invoice” на `ServiceAct`:
  - создаёт Invoice по действию бухгалтера
  - после создания: `schedule.status → Invoiced`

## C) Client access (портал/телеграм): “не видит акты/УПД”

### C1) User Permission
- Клиенту выдаём `User Permission` на `Contract` (Contract достаточно).
- Фильтрация видимости Contract дополнительно по `is_portal_visible=1`.

### C2) Права ролей
Для клиентской роли:
- `ServiceAct`: No Read
- `Sales Invoice`: No Read
- `ActSchedule`: Read без суммы:
  - `planned_amount` в `permlevel=1`
  - клиентской роли дать доступ только к `permlevel=0`

Клиенту показываем:
- `Contract` (свои)
- `ServiceObject` через `ContractServiceObject`
- `ServiceRequest/Issues` (по contract/project)

### C3) Telegram
- Telegram user → User Permission на `Contract/Project`
- Команды:
  - список доступных контрактов
  - заявки по контракту
  - календарь (ActSchedule) — только статусы/периоды, без сумм

## D) ferum_custom: изменения

### D1) ServiceProject OFF
- убрать из Workspaces/menu
- убрать использование в новых формах
- новые ссылки всегда на `Project + Contract`

### D2) Удалить “ServiceObject belongs to project”
- любые поля `service_object.project` не использовать
- любые проверки “объект уже в другом проекте” удалить
- единственная привязка: `ContractServiceObject`

### D3) Sync Contract → Project (хуки)
Реализовать:
- on Contract becoming Active: create Project (если нет)
- on Contract update: sync Project fields
- enforce 1:1 (второй Project на тот же Contract запрещён)

## E) Naming Series
- Contract: `CT-.YYYY.-.#####` (Property Setter на `Contract.autoname`)
- Project: `PRJ-.YYYY.-.#####` (добавить в options `Project.naming_series`)
- ServiceAct: `ACT-.YYYY.-.#####`
- ActSchedule: `SCH-.YYYY.-.#####`

## F) Минимальный набор серверной логики

Чтобы TODO реально закрывался, достаточно 6 функций/хуков:
1. `validate_contract_party_is_customer(contract)`
2. `ensure_project_for_contract(contract)` (create + enforce 1:1)
3. `sync_project_from_contract(contract, project)`
4. `validate_project_has_contract(project)` + `validate_project_unique_contract(project)`
5. `generate_act_schedule(contract_or_project, frequency, mode)` (кнопка/API)
6. `on_service_act_signed(service_act)` (create invoice if needed + update schedule)

