# Ferum ERP — описание бизнес‑процессов (AS‑IS)

Дата: 2026‑02‑10  
Контур: ERPNext/Frappe v15 + кастомное приложение `ferum_custom`.

Документ фиксирует **текущую реализованную модель (AS‑IS)**: какие процессы поддерживаются, какими объектами данных (DocType) они представлены, какие роли участвуют, и где находятся ключевые автоматизации/интеграции.

> Примечание: часть старых процессов/сущностей (`Service Project`, `Service Object`) сохранена для обратной совместимости и истории, но основной управленческий контур смещён в стандартный ERPNext `Project` (с кастомными полями P0) и таблицу объектов проекта `Project Site`.

## 1) Сквозная цепочка процессов (карта)

```mermaid
flowchart LR
  A[Тендер/Договор] --> B[Проект (Project)]
  B --> C[Объекты проекта (Project Site)]
  C --> D[Заявки (Service Request)]
  D --> E[Отчёт о работах (Service Report)]
  E --> F[Финансы (Invoice/Sales Invoice)]
  B --> G[Документооборот проекта (File → Google Drive)]
  D --> H[Фото/вложения по заявкам]
  subgraph Integrations
    T[Telegram bot] --- D
    GD[Google Drive] --- G
    V[Vault] --- CFG[Settings layer]
  end
```

## 2) Роли (кто делает что)

Ключевые роли в текущем контуре:

- **Administrator / System Manager** — полный доступ, настройки, миграции, интеграции.
- **Project Manager / Projects Manager** — ведение проекта, контроль процессов, документы/коммуникации, доступ к проектам.
- **Office Manager / Ferum Office Manager** — документооборот (почта/сканы), помощь в операционной работе.
- **Service Engineer** — работа по заявкам, фото/обследования, доступ к объектам и проектам в своей зоне.
- **Client** — ограниченный доступ к проектным документам (разрешённые типы), заявкам/статусам (в рамках доступных проектов).

Механика ограничения доступа на уровне данных (AS‑IS):

- `Project.project_manager == user`
- `Project.users` (стандартная таблица участников проекта)
- `Project Site.default_engineer == user`
- `User Permission` на `Project`/`Customer` и связь `Contact.user -> Customer`

Реализация: `ferum_custom/security/project_access.py`.

## 3) Объектная модель (DocTypes) — что является “истиной”

### Управляющий контур

- **Contract** (стандартный ERPNext) — договор с заказчиком (в системе принудительно `party_type=Customer`).
- **Project** (стандартный ERPNext) — главный контейнер управления; дополнен кастомными полями P0 (этапы, дедлайны, чек‑листы, исходящая почта, ссылки на Drive).
- **Project Site** (дочерняя таблица, `istable=1`) — “объект” в рамках проекта: имя/адрес/инженер/ссылка на Drive.

### Операционный сервисный контур

- **Service Request** — заявка (тикет) на обслуживание:
  - новый контур: `erp_project` (Link Project) + `project_site` (Link Project Site)
  - legacy контур: `service_object` (Link Service Object)
- **Service Report** — отчёт/акт по заявке (табличные работы + документы).

### Финансы (AS‑IS)

- **Invoice** (кастомный DocType) — внутренний трекинг счетов:
  - может связываться с `Contract`, `Project` (кастом‑поле `erpnext_project`), `Sales Invoice`
  - при submit умеет синхронизироваться в Google Sheets (опционально; зависит от наличия библиотеки `gspread`)

### Документы (AS‑IS)

- **File** (стандартный DocType) — используется как единый механизм учёта файлов.
- “Документы проекта/контракта” реализованы как `File`, привязанные к `Project` через `attached_to_doctype=Project` и `attached_to_field=ferum_project_documents`, с обязательными метаданными:
  - `ferum_doc_title` (Наименование документа)
  - `ferum_doc_type` (Тип документа)
  - `ferum_contract` (опционально)
  - `ferum_drive_file_id` (идентификатор файла в Drive)

Реализация: `ferum_custom/api/project_documents.py`, `ferum_custom/services/project_documents.py`, `ferum_custom/security/file_permissions.py`.

## 4) Процесс BP‑01: Договор → Проект (инициация)

**Цель:** создать управляемый проект с ответственными, сроками и структурой данных под цикл работ.

**Триггер (AS‑IS):**

- Договор `Contract` переводится в `status=Active` → создаётся/синхронизируется `Project` (1:1).

**Основные шаги:**

1) Создать/актуализировать `Contract` (в системе закрепляется `party_type=Customer`).  
2) При `Active` система создаёт `Project` и связывает его с `Contract` (`Project.contract`), синхронизирует базовые поля (customer/company/PM/dates).  
3) В `Project` ведётся этап `ferum_stage` (P0) и контрольные дедлайны/гейты (если включено `ferum_p0_enabled`).  

**Автоматизации:**

- enforce party_type/customer: `ferum_custom/services/contract_project_sync.py`
- валидация уникальности `Contract ↔ Project`: `ferum_custom/services/contract_project_sync.py`
- P0‑гейты/автопродвижение/дефолты дедлайнов: `ferum_custom/services/project_full_cycle.py`
- ежедневные эскалации по дедлайнам: `ferum_custom/services/project_escalations.py`

## 5) Процесс BP‑02: Объекты проекта (Project Sites)

**Цель:** зафиксировать все обслуживаемые объекты/адреса внутри проекта и назначить инженеров.

**AS‑IS:**

- Объекты проекта ведутся как строки таблицы `Project Site` внутри `Project`.
- Для инженеров доступ к проекту может открываться через назначение `Project Site.default_engineer`.

**Автоматизации/интеграции:**

- Для каждого объекта можно создать Drive‑папку (см. BP‑04 и runbook структуры Drive).

## 6) Процесс BP‑03: Документооборот проекта/контракта (сканы)

**Цель:** юридически корректное хранение документов проекта (договоры, закрывающие, корреспонденция и т.д.) с контролем доступа.

**Правила AS‑IS:**

- Загрузка **разрешена только в контексте проекта** (Project обязателен).
- В ERP создаётся запись `File` с метаданными + ссылкой на Drive (`file_url` = webViewLink).
- Физическое хранение — Google Drive, структура детерминирована и одинакова для всех проектов (русские имена папок).

**Типы документов (AS‑IS):**

Справочник типов фиксирован в коде: `ferum_custom/services/project_documents_config.py`.

**Права доступа (AS‑IS):**

- Upload: роли из `UPLOAD_ROLES` (PM/Office/System Manager).
- View:
  - внутренние пользователи — в рамках доступа к проекту,
  - `Client` — только разрешённые типы (`CLIENT_ALLOWED_TYPES`).

**Где смотреть структуру папок (актуально):**

- `docs/runbooks/google_drive_structure.md` (версия `ru_v1`).

## 7) Процесс BP‑04: Заявки на обслуживание (Service Request)

**Цель:** принимать, распределять и контролировать выполнение работ по объектам проекта.

**Источники создания (AS‑IS):**

- ERPNext Desk (ручной ввод офисом/PM).
- Telegram bot (создание заявок/просмотр, в рамках доступных проектов).
- Регламентные заявки: ежедневный scheduler генерирует заявки по графику.

**Ключевые данные заявки (AS‑IS):**

- `erp_project` + `project_site` (предпочтительно)
- `service_object` (legacy, сохраняется для истории/части интеграций)
- `assigned_to`, `priority`, `status`, `description`

**Автоматизации (AS‑IS):**

- Уведомления о создании/смене статуса (Telegram/email, best‑effort): `ferum_custom/notifications.py`
- Генерация регламентных заявок: `ferum_custom/services/service_schedule.py`

## 8) Процесс BP‑05: Отчёт о работах (Service Report)

**Цель:** зафиксировать выполненные работы и доказательную базу (таблица работ + документы).

**AS‑IS:**

- `Service Report` создаётся и связывается с `Service Request`.
- Содержит:
  - `Service Report Work Item` — перечень работ/объёмов/стоимости
  - `Service Report Document Item` — документы/файлы (сканы/фото)
- При необходимости используется для дальнейшего выставления счетов/закрывающих.

Уведомления: `ferum_custom/notifications.py` (события `Service Report`).

## 9) Процесс BP‑06: Финансовые документы (Invoice / Sales Invoice)

**Цель:** вести внутренний реестр выставленных и полученных счетов + связать их с проектами.

**AS‑IS:**

- Основной реестр — кастомный DocType `Invoice`:
  - контрагент (Customer/Subcontractor),
  - суммы/даты/статусы,
  - связь с `Contract` и `Project` (через кастом‑поле `erpnext_project`, если создано на сайте),
  - опциональная связь с `Sales Invoice`.
- При submit `Invoice` выполняется синхронизация в Google Sheets (если в окружении установлен `gspread` и доступна учётка).

## 10) Интеграции (где “стыкуются” процессы)

### Telegram bot (операции + self‑service)

- Команды / работа через webhook/polling.
- Доступ к проектам берётся из ERP (Project membership + права).
- Основной API для бота: `ferum_custom/api/telegram_bot.py`.
Runbook: `docs/runbooks/telegram_bot.md`.

### Google Drive (единое хранилище документов)

- Папки проекта и документов создаются детерминированно.
- Загрузка проектных документов идёт сразу в Drive; в ERP хранится ссылка.
Runbook: `docs/runbooks/google_drive_structure.md`.

### Vault (единый источник секретов/конфигурации)

- Реализован unified settings слой: `frappe.conf` → env → Vault KV → `Ferum Custom Settings`.
- Есть ручные инструменты миграции в Vault и cutover.
Runbook: `docs/runbooks/vault.md`.

## 11) Контроль качества процесса (операционная проверка)

- Runtime audit (smoke): `bench --site <site> execute ferum_custom.setup.audit.run --kwargs "{'write_report': 1}"`
  - проверяет импорты хуков, мету Doctype/Report, ссылки workspace, health интеграций.
Runbook: `docs/runbooks/runtime_audit.md`.
