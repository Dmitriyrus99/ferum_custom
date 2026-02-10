# Ferum ERP — описание бизнес‑процессов (AS‑IS, актуально по коду)

Дата: 2026‑02‑10  
Контур: ERPNext/Frappe v15 + кастомное приложение `ferum_custom`.

Документ фиксирует **реально реализованные процессы** и их привязку к объектной модели (DocType), хукам, API и интеграциям.

См. также:

- целевая модель объектов: `docs/architecture/project_site_tobe.md`
- “Project как контейнер”: `docs/architecture/project_as_container.md`
- runbook Drive‑структуры: `docs/runbooks/google_drive_structure.md`

---

## 1) Контуры системы (каналы и интерфейсы)

**ERPNext Desk (основной интерфейс):**

- управление договорами/проектами/объектами
- создание и обработка заявок (Service Request)
- оформление отчётов о работах (Service Report)
- реестр счетов (Invoice) и актирование (ServiceAct/ActSchedule)
- загрузка и просмотр документов проекта (File → Google Drive)

**Telegram‑бот (self‑service + поле):**

- регистрация пользователя через email‑код (ERP хранит связку chat_id ↔ User)
- выбор проекта/объекта и создание заявок
- список “мои заявки”
- загрузка вложений к заявке и “обследование” (фото/файлы) прямо в Google Drive

**Google Drive (единое хранилище):**

- детерминированная структура папок проекта + папок объектов
- проектные документы загружаются напрямую в Drive, а в ERP хранится корректный `file_url` (webViewLink)

**Vault (опционально, для секретов/конфигурации):**

- единый typed‑settings слой читает настройки из `frappe.conf` → `os.environ` → Vault KV → `Ferum Custom Settings`

---

## 2) Роли и модель доступа (AS‑IS)

Ключевые роли:

- **Administrator / System Manager** — полный доступ, настройки, миграции, интеграции.
- **Project Manager / Projects Manager** — управление проектами, доступ к документам, контроль заявок.
- **Office Manager / Ferum Office Manager** — документооборот, помощь в регистрации/заявках.
- **Engineer / Service Engineer** — доступ к заявкам и объектам в зоне ответственности.
- **Client** — ограниченный доступ в рамках своего клиента и доступных проектов/документов.

Базовая логика доступа к проекту (используется и в API/боте):

- `Project.project_manager == user`
- `Project.users` содержит пользователя
- пользователь назначен инженером на объект (`Project Site.default_engineer`)
- `User Permission` на `Project` или на `Customer` (в т.ч. через `Contact.user → Customer`)

Реализация: `ferum_custom/security/project_access.py`, плюс PQC/has_permission для `Project Site` и журнала:
`ferum_custom/security/project_site_permissions.py`.

---

## 3) Объектная модель (DocTypes) — на чём держатся процессы

### 3.1 Управляющий контур

- **Contract** (ERPNext) — договор с заказчиком; валидация `party_type=Customer`.
  - хуки: `ferum_custom/services/contract_project_sync.py`
- **Project** (ERPNext) — управленческий контейнер, 1:1 связан с Contract (для Active).
  - авто‑создание/синхронизация из Contract: `ensure_project_for_contract`
  - P0‑цикл/гейты/эскалации (если включён флаг `ferum_p0_enabled`): `ferum_custom/services/project_full_cycle.py`, `ferum_custom/services/project_escalations.py`

### 3.2 Объекты обслуживания (Project Site)

Сейчас поддерживаются **две формы хранения** (для обратной совместимости):

- **`Project Site` (truth, `istable=0`)** — основной объект обслуживания, на который ссылаются новые процессы.
- **`Project Site Row` (legacy child table, `istable=1`)** — строки в `Project.project_sites`, оставлены для совместимости/истории.

Миграции (идемпотентно):

- переименование legacy `Project Site` → `Project Site Row`: `ferum_custom/patches/v15_10/rename_legacy_project_site_doctype.py`
- перенос rows → truth sites + ремонт имен (чтобы `Service Request.project_site` не “ломался”):  
  `ferum_custom/patches/v15_10/migrate_project_site_row_to_truth.py`,  
  `ferum_custom/patches/v15_10/repair_project_site_truth_names.py`

### 3.3 Операционный сервисный контур

- **Service Request** — заявка:
  - привязка: `erp_project` (Project) + `project_site` (Project Site)
  - legacy‑поле: `service_object` (Service Object) остаётся для совместимости ряда сценариев
  - фиксация источника/времени: `registered_datetime`, `reported_datetime`, `source_channel`, `source_reference`, `source_evidence_file`
  - SLA: вычисляется от `reported_datetime` (если задано) иначе от `registered_datetime/creation`
  - серверные проверки: `ferum_custom/ferum_custom/doctype/service_request/service_request.py`
- **Service Report** — отчёт о работах:
  - содержит `work_items` и `documents`
  - при `on_submit` закрывает заявку до статуса `Completed`: `ferum_custom/ferum_custom/doctype/service_report/service_report.py`

### 3.4 Актирование и счета

- **ActSchedule** — планирование актов по периодам (на базе Contract).
- **ServiceAct** — акт; при переходе в `Signed` выполняет связанные действия (в т.ч. обновление статуса расписания, опционально создание Sales Invoice).
  - логика: `ferum_custom/services/acts.py`
- **Invoice** (кастомный реестр счетов) — статусы Draft/Sent/Paid/… + опциональная синхронизация в Google Sheets (если установлен `gspread`).
  - логика: `ferum_custom/ferum_custom/doctype/invoice/invoice.py`

### 3.5 Документы проекта (File → Google Drive)

Функциональность “Документы проекта” реализована **через стандартный DocType `File`** с метаданными (Custom Fields) и серверной валидацией:

- обязательные поля: `ferum_doc_title`, `ferum_doc_type`
- хранение: `file_url` указывает на Google Drive; `ferum_drive_file_id` хранит id
- типы документов: фиксированный перечень в `ferum_custom/services/project_documents_config.py`
- серверная валидация File: `ferum_custom/services/project_documents.py`
- API загрузки/листа: `ferum_custom/api/project_documents.py`

---

## 4) Сквозные бизнес‑процессы (AS‑IS)

### BP‑01 — Договор → Проект (Contract → Project 1:1)

**Цель:** обеспечить единый управленческий контейнер Project для активного договора.

1) Создаётся/обновляется `Contract`.
2) При `status=Active` система:
   - валидирует `party_type=Customer`
   - создаёт/находит связанный `Project` (строго 1:1)
   - синхронизирует поля Customer/Company/PM/даты

Код: `ferum_custom/services/contract_project_sync.py` (hooks см. `ferum_custom/hooks.py`).

### BP‑02 — Управление проектом (P0‑цикл, опционально)

**Цель:** “проект под контролем” через этапы/гейты/дедлайны и эскалации.

- включается флагом `Project.ferum_p0_enabled=1`
- гейты стадий проверяются на `Project.validate`
- ежедневный scheduler шлёт эскалации по дедлайнам PM/директору (email + telegram best‑effort)

Код: `ferum_custom/services/project_full_cycle.py`, `ferum_custom/services/project_escalations.py`.

### BP‑03 — Объекты (Project Site)

**Цель:** иметь однозначные “объекты обслуживания” с адресами и назначением инженера.

- truth объект: `Project Site` (используется в новых заявках/уведомлениях/Drive‑папках)
- legacy таблица `Project.project_sites` остаётся как историческая форма ввода/хранения

Проверки:

- принадлежность объекта проекту проверяется при создании заявки (Desk/API/бот): `ferum_custom/utils/project_sites.py`

### BP‑04 — Заявки (Service Request)

**Источники создания:**

- ERPNext Desk (офис/PM)
- Telegram bot (через ERP API, с проверками доступа)
- регламент (scheduler) — текущая реализация генерирует заявки по legacy `service_object` (требует постепенной модернизации под `project_site`)

**Ключевая логика:**

- статусы и переходы валидируются на сервере
- SLA дедлайн считается от `reported_datetime` (если задан), иначе от регистрации
- для внешних источников при разнице `reported_datetime` vs `registered_datetime` требуется `source_reference` или `source_evidence_file`

Код: `ferum_custom/ferum_custom/doctype/service_request/service_request.py`,  
уведомления: `ferum_custom/notifications.py`,  
регламент: `ferum_custom/services/service_schedule.py` (legacy).

### BP‑05 — Отчёт о работах (Service Report) → закрытие заявки

**Цель:** документировать выполненные работы и закрыть заявку корректно.

1) Создаётся `Service Report` по заявке.
2) В `validate`:
   - пересчитываются суммы work‑items
   - проверяется наличие вложений (Document Items)
3) При `on_submit`:
   - `Service Request.linked_report = Service Report`
   - `Service Request.status = Completed`

Код: `ferum_custom/ferum_custom/doctype/service_report/service_report.py`.

### BP‑06 — Документы проекта (сканы/письма/акты) в Google Drive

**Цель:** юридически корректное и структурированное хранение документов по проекту.

1) Пользователь загружает файл через UI “Документы проекта”.
2) Сервер:
   - проверяет роль + доступ к проекту
   - создаёт/проверяет структуру Drive‑папок проекта
   - загружает файл в Drive в детерминированную категорию
   - создаёт `File` с метаданными и `file_url=Drive webViewLink`
3) Для Client‑пользователя выдача ограничивается типами (`CLIENT_ALLOWED_TYPES`).

Код: `ferum_custom/api/project_documents.py`, `ferum_custom/services/project_documents.py`,  
структура папок: `ferum_custom/api/project_drive.py` + `docs/runbooks/google_drive_structure.md`.

### BP‑07 — Telegram‑бот (операционные сценарии)

**Цель:** снизить ручной ввод и ускорить работу инженеров/клиентов.

- регистрация: `/register <email>` → код на email → создание `Telegram User Link`
- “проекты/объекты”: списки фильтруются по ERP‑правам (Project membership + правила доступа)
- создание заявки: проект → объект → заголовок/приоритет/описание → `Service Request`
- вложения/обследование: файлы/фото уходят в Drive папку объекта/раздела и фиксируются ссылками

ERP API: `ferum_custom/api/telegram_bot.py`  
код бота: `ferum_custom/integrations/telegram_bot/*`

---

## 5) Автоматизации и контроль (что проверяет целостность)

- хуки DocType: `ferum_custom/hooks.py`
- runtime audit: `bench --site <site> execute ferum_custom.setup.audit.run --kwargs \"{'write_report': 1}\"`
  - импорты hook‑таргетов
  - мета doctypes/reports/flows
  - единичные checks по Workspaces (“Объекты”)
  - health интеграций (wkhtmltopdf/telegram/fastapi/vault/drive)

Отчёты audit сохраняются в `docs/audit/`.

---

## 6) Legacy/ограничения (важно для эксплуатации)

- `Service Project` / `Service Object` сохранены как legacy‑контур (часть сценариев/регламент).
- Генератор регламентных заявок (`service_schedule.py`) ещё опирается на `service_object` и требует модернизации под `project_site`.
- FastAPI backend содержит часть API/логики и совместимостные обвязки; не все endpoint’ы реализованы как “боевые” (см. `ferum_custom/integrations/fastapi_backend/routers/*`).
