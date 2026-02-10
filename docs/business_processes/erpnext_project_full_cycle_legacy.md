# ERPNext Project: полный цикл (Tender → Contract → Start → Primary docs → Closing docs → Payment → Contractors) (legacy)

Этот документ фиксирует **целевую модель процесса** (как должно быть) и одновременно объясняет **как сейчас устроены модули/хуки в `ferum_custom`**, чтобы было понятно где “стыкуется” новый процесс.

## 0) Текущая архитектура (as‑is) vs целевая (to‑be)

### As‑is в коде `ferum_custom`

Система сейчас реально опирается на кастомные сущности сервиса:

- `Service Project` + `Service Object` — “контракт/проект обслуживания” и “объект обслуживания”
- `Service Request` — заявки (тикеты) по объекту
- `Service Report` — отчёты/акты по заявке (при submit закрывают заявку)
- `Service Maintenance Schedule` — регламентный график, который **ежедневным scheduler job** создаёт заявки

Точки автоматизаций:

- Document Events: `Service Request`/`Service Report`/`Contract`/`Project` → хуки в `apps/ferum_custom/ferum_custom/hooks.py`
- Scheduler: daily → `ferum_custom.services.service_schedule.generate_service_requests_from_schedule`
- Telegram‑уведомления и интеграции → `ferum_custom/notifications.py`, `telegram_bot/*`

Важный нюанс: в репозитории есть код для модели **Contract → Project 1:1**, но на конкретном сайте это может быть не применено (если custom field `Project.contract` не создан/патч не прогнан).

### To‑be (целевая): ERPNext `Project` — главный объект управления

Целевая модель процесса требует, чтобы:

- **ERPNext `Project`** стал “контейнером” всего цикла: тендер → контракт → старт работ → первичка → закрывающие → оплата → подрядчики.
- Сервисные сущности (`Service Request`, `Service Report`, фото/вложения) либо:
  - (вариант 1) остаются как “ticketing‑слой” и получают ссылку на `Project`, либо
  - (вариант 2) постепенно заменяются стандартными ERPNext Issue/Task (позже).

Рекомендуемая стратегия внедрения:

- P0: добавить workflow/гейты и таблицы/поля в `Project`, не ломая текущий сервисный контур.
- P1: подключить Telegram/Drive к новым данным `Project`.
- P2: вынести расчёты с подрядчиками/инструмент в отдельные DocType и сделать финансы “по‑взрослому”.

## 1) Участники процесса и роли (кто за что отвечает)

- PM (Project Manager): ведёт проект, общается с заказчиком, решает вопросы подряда, отвечает за первичку/акты.
- Тендерный специалист: заводит/передаёт данные тендера, инициирует юр.проверку.
- Юрист: проверка проекта договора (статусы согласования).
- Офис‑менеджер: отправка пакетов Почтой РФ, хранение треков/описи/сканов.
- Директор: контрольные approvals (подрядчик, акты/ведомость и т.п.), эскалации по дедлайнам.
- Инженер/подрядчик: первичное обследование, фото, выполнение заявок, отчётность.
- Бухгалтерия: счета/закрывающие/контроль оплаты.
- Заказчик (клиент): контакты, получение документов, оплата, заявки через бот.

## 2) Объекты данных в целевой модели (что хранится где)

### 2.1 ERPNext `Project` (главный)

В `Project` добавляются блоки/поля/таблицы:

1) **Источник победы / тендер**
   - `tender_source`
   - `eis_etp_url` (обяз.)
   - `tender_customer_name` (обяз.)
   - `tender_price` (обяз.)
   - `tender_term` (обяз.)
   - `tender_protocol_date` (обяз., триггер старта)

2) **Контакты заказчика** (таблица `Customer Contacts`)
   - `fio` (обяз.)
   - `position` (обяз.)
   - `phone` (обяз.)
   - `official_email` (обяз.) + `official_email_verified` (Check)
   - `legal_address` (обяз.)
   - `postal_address` (обяз.)
   - `object_addresses` (как Table или отдельный DocType `Project Site`)
   - `operational_contact_*` (опционально)

3) **Контракт / проверка (до подписания)**
   - `contract_draft_reviewed` (Check)
   - `subcontracting_allowed` (Allowed/Forbidden/Unknown)
   - `legal_review_required` (Check)
   - `legal_review_status` (Draft/Sent/Approved/Returned)
   - `contract_signed_date` (Date)

4) **Подрядчик и форма отношений**
   - `execution_mode` (In‑house/Self‑employed/GPH/Subcontractor)
   - `subcontractor_selected` (Check)
   - `subcontractor_party` (Supplier/Contractor)
   - `subcontractor_contact_phone`
   - `subcontractor_contract_signed` (Check) + `subcontractor_contract_file`
   - `director_approved_subcontractor` (Check, гейт)

5) **Пакет документов / Почта России** (таблица `Outbound Mail Items`)
   - `package_type`, `sent_date`, `sent_by` (auto), `russian_post_tracking`, `inventory_scan`, `receipt_scan`, `status`

6) **Первичное обследование и фото**
   - `start_work_date` (если вводится)
   - `photo_survey_deadline` = `start_work_date + N`
   - `photo_survey_format` (Checklist+Photo / Photo‑only)
   - `drive_folder_url`
   - таблица `Survey Checklist`: `section`, `required`, `done`, `evidence_link`

7) **Акт первичного обследования и ведомость**
   - `initial_survey_act_due`
   - `initial_survey_act_file`
   - `defects_list_file`
   - `director_approval_required` (true)
   - `director_approved` (гейт)
   - `sent_to_customer_date`
   - `if_customer_ignored_trigger_mail_task` (auto)

8) **Финансы по периодам** (таблица `Billing Periods`)
   - `period_type`, `period_start/end`
   - `docs_prepare_window`, `docs_send_window`
   - `invoice_sent_date`, `act_sent_date`
   - `originals_sent_tracking` (Link на Outbound Mail Item)
   - `customer_docs_received_confirmed`
   - `payment_due_date`, `payment_status`, `payment_control_notes`

9) **Расчёты с подрядчиками** (минимум в Project, лучше вынести)
   - `contractor_payment_due_rule`, `contractor_docs_received`, `originals_received`, `contractor_payment_request_link`

10) **Инструмент** (лучше отдельным DocType `Tool Issue`)

### 2.2 Связанные сущности

- `Contract` (если используем): хранит юридическую часть (и служит источником для `Project.contract` по модели 1:1).
- `Supplier`/`Contractor` (подрядчик).
- `Contact`/`Address` (для нормализации контактов/адресов).
- `Service Request`/`Service Report` (ticketing) — как слой исполнения заявок; связывается с `Project` и `Project Site`.
- `CustomAttachment` — хранит файл и (опционально) ссылку/ID в Google Drive.

## 3) Workflow `Project` (статусы + гейты)

Целевые статусы:

1. Tender Won
2. Contact Established
3. Contract Signed
4. Contractor Selected/Contracted
5. Initial Document Package Sent
6. Primary Survey Completed
7. Act & Defects Sent
8. Invoice/Act Sent
9. Customer Received Docs Confirmed
10. Payment Received

Гейты переходов (валидации на уровне `Project.validate` + Workflow transitions):

- Tender Won → Contact Established:
  - заполнена таблица контактов, `official_email` обязателен, `official_email_verified=true`
  - зафиксирован факт отправки приветственного письма (`welcome_email_sent_date` + лог)

- Contact Established → Contract Signed:
  - `contract_signed_date` заполнена
  - `legal_review_status=Approved` (или override директором)

- Contract Signed → Contractor Selected/Contracted:
  - `subcontracting_allowed != Unknown`
  - если Allowed + subcontractor_selected=true:
    - `director_approved_subcontractor=true`
    - `subcontractor_contract_signed=true` и файл договора приложен
  - если Forbidden:
    - `execution_mode in {In-house, Self-employed, GPH}` и подтверждение директора сценария

- Initial Document Package Sent:
  - существует минимум 1 `Outbound Mail Item` с треком и сканами

- Primary Survey Completed:
  - чек‑лист выполнен (или photo-only подтверждён PM)
  - `drive_folder_url` задан

- Act & Defects Sent:
  - акт/ведомость загружены
  - `director_approved=true`
  - зафиксирована отправка заказчику (email/почта)

- Invoice/Act Sent:
  - период создан
  - документы сформированы/приложены
  - факт отправки отмечен

- Payment Received:
  - подтверждение оплаты (ручное/интеграция)

## 4) Автоматизации (что делает система)

### 4.1 При создании `Project` в статусе Tender Won

Автоматически:

- ToDo для PM:
  - “Ознакомиться с проектом договора/ТЗ”
  - “Запросить контакты заказчика”
- ToDo тендерному специалисту:
  - “Передать проект контракта юристу на проверку”
- Уведомление директору (внутреннее уведомление/Telegram при включении)

Реализация в коде:

- `doc_events["Project"]["after_insert"]` → генерация ToDo
- `doc_events["Project"]["on_update"]` → реакция на смену статуса/даты протокола

### 4.2 При внесении официального email и контактов

- Кнопка “Сформировать приветственное письмо”:
  - рендерит email template
  - отправляет вручную PM
  - факт отправки фиксируется: `welcome_email_sent_date` + запись в Communication/Comment
  - CC: директор (жёстко)

### 4.3 Подряд / запрет подряда

- Блокировать:
  - `subcontracting_allowed=Forbidden` и `execution_mode=Subcontractor`
- Требовать:
  - `director_approved_subcontractor` + файл договора, если Allowed и выбран подрядчик

### 4.4 Почта России

- При добавлении `Outbound Mail Item`:
  - `sent_by` автозаполняется текущим пользователем (если роль Office Manager)
  - при наличии трека и обязательных сканов система может автоматически “поднять” статус проекта → Initial Document Package Sent

### 4.5 Дедлайны и эскалации (P0 критично)

Ежедневный scheduler job:

- проверяет дедлайны:
  - “Подрядчик выбран/заключён”
  - “Первичное обследование выполнено”
- если просрочено и статус ниже нужного:
  - уведомление директору + PM (Telegram/Email/Desk Notification)

### 4.6 Фото и Google Drive

На `Contract Signed` или `Start Work Date`:

- создаётся структура папок на Drive:
  - `/Проекты/<PRJ>/<Объект 1..N>/`
- сохраняются ссылки:
  - `Project.drive_folder_url`
  - для каждого объекта — `Project Site.drive_folder_url` (если вынесено)

Инженер/бот:

- бот принимает фото → сохраняет как `File`/`CustomAttachment` → грузит в Drive → возвращает ссылку
- ссылка прикрепляется в `Survey Checklist.evidence_link`

### 4.7 Оплата заказчика

MVP:

- ручной `payment_status` + напоминания

Позже:

- импорт выписки (MT940/банк API) и автосверка

### 4.8 Оплата подрядчика

P2:

- отдельный DocType `Contractor Payment Request` + approval директором
- обязательные документы/чеки + отметка оригиналов

### 4.9 Инструмент

P2:

- отдельный DocType `Tool Issue`, связанный с `Project`
- контроль возврата на закрытии проекта

## 5) Где это должно жить в `ferum_custom` (модульная карта реализации)

Минимальный P0‑каркас в `apps/ferum_custom/ferum_custom`:

- `patches/v15_xx/add_project_tender_workflow_fields.py`:
  - `create_custom_fields({... "Project": [...]})`
  - create child table DocTypes (если ещё нет) или использовать fixtures
  - добавить/обновить Workflow `Project` (через insert в `Workflow`)

- `services/project_workflow.py`:
  - проверки гейтов по статусам (validate)
  - вычисление дедлайнов
  - хелперы “достаточность данных”

- `services/project_todos.py`:
  - генерация ToDo на `after_insert` и on status transitions

- `services/project_escalations.py`:
  - ежедневная проверка дедлайнов + уведомления

- `integrations/drive/project_folders.py`:
  - создание папок по проекту/объектам

- Telegram:
  - бот/ERP API должны уметь выбирать `Project` и `Project Site` (вместо Service Project/Object)

## 6) Что сделать первым шагом (P0, без дополнительных согласований)

1) Зафиксировать Workflow `Project` (статусы + гейты) **ровно как в целевой модели**.
2) Добавить в `Project` P0‑блоки (тендер, контакты, подряд, почта, первичка, акты/ведомость, биллинг‑периоды) как Custom Fields + child tables.
3) Реализовать автоматику P0:
   - ToDo при создании/смене статусов
   - дедлайны + ежедневные эскалации директору
   - фиксация приветственного письма (поле + кнопка/шаблон)
   - Outbound Mail Items как триггер стадии “Initial Document Package Sent”
