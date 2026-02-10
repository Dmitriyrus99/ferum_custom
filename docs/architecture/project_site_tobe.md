# TO‑BE: `Project Site` как «истина» (переход от child table)

Дата: 2026‑02‑10

## 1) Контекст

Сейчас в Ferum используется модель:

- ERPNext `Project` как основной контейнер.
- `Project Site` как **child table** (DocType `Project Site`, `istable=1`) внутри `Project.project_sites`.
- `Service Request.project_site` — `Link` на **строку** child‑таблицы (`Project Site.name`).

Цель TO‑BE (по согласованному плану):

- `Project` сделать «тонким» контейнером (контракт/участники/аналитика).
- `Project Site` сделать **самостоятельным DocType** (не `istable`) и перенести на него операционную «истину».
- Добавить журнал эксплуатации (электронный + учёт бумажного) и фиксацию момента заявки (источник/время).

Важно: в текущем репозитории **уже существует** DocType `Project Site` как child‑таблица, поэтому для TO‑BE потребуется миграция/переименование legacy‑структуры.

## 2) AS‑IS модель данных (как сейчас)

### 2.1 `Project.project_sites` (Table)
Создаётся патчем `ferum_custom/patches/v15_9/add_project_full_cycle_p0.py` и хранит объекты обслуживания проекта.

### 2.2 DocType `Project Site` (legacy, `istable=1`)
Файл: `ferum_custom/ferum_custom/doctype/project_site/project_site.json`

Поля (legacy child row):
- `site_name` (Data, reqd)
- `address` (Small Text, reqd)
- `drive_folder_url` (Data)
- `default_engineer` (Link User)
- `notes` (Small Text)

### 2.3 `Service Request`
- `erp_project` (Link Project) — сейчас **reqd=1** в JSON.
- `project_site` (Link Project Site) — ссылается на строку child‑таблицы.
- `service_object` (Link Service Object) — legacy.

Валидация в `ferum_custom/ferum_custom/doctype/service_request/service_request.py` проверяет, что выбранный `project_site` принадлежит выбранному `erp_project` через поле `parent` у child‑строки.

## 3) Карта использования (Task 1 — репо‑скан)

Ниже — **все места**, где сейчас фигурируют `Project Site`/`project_site`/`project_sites` (по `rg`‑скану).

### 3.1 Мета/DocTypes
- `ferum_custom/ferum_custom/doctype/project_site/project_site.json` — legacy child DocType (`istable=1`).
- `ferum_custom/ferum_custom/doctype/service_request/service_request.json` — поле `project_site` (Link → `Project Site`) и `service_object` (legacy).
- `ferum_custom/ferum_custom/doctype/service_request/service_request.py` — проверка принадлежности `Project Site` к `Project` через `parent`.
- `ferum_custom/ferum_custom/doctype/service_request/test_service_request.py` — тесты завязаны на legacy child rows.

### 3.2 Google Drive (структура/папки)
- `ferum_custom/api/project_drive.py` — `ensure_drive_folders()`:
  - создаёт корневую структуру папок проекта;
  - создаёт папку на каждый `Project Site` (child row) и пишет `Project Site.drive_folder_url`.

### 3.3 Telegram bot
- `ferum_custom/api/telegram_bot.py`:
  - `list_objects()` читает child‑строки `Project Site` по `parent=Project`;
  - `create_service_request()` принимает `project_site` (или legacy `service_object`), проверяет `parent`, создаёт `Service Request`;
  - `upload_survey_evidence()` использует `Project Site.drive_folder_url` для загрузки в Drive.
- `ferum_custom/integrations/telegram_bot/handlers/commands.py`:
  - передаёт `project_site` в API при загрузке evidence (опрос/обследование).

### 3.4 Безопасность/доступ
- `ferum_custom/security/project_access.py`:
  - расширяет доступ к `Project` через `Project Site.default_engineer` (SQL по `tabProject Site` с `parent=Project`).

### 3.5 Уведомления
- `ferum_custom/notifications.py`:
  - обогащает контекст заявки, пытаясь извлечь `site_name/address/default_engineer/parent` из `Project Site`.

### 3.6 Отчёты/Workspace
- `ferum_custom/ferum_custom/report/project_sites/project_sites.py` — Script Report `Project Sites` через SQL по `tabProject Site` (child rows).
- `ferum_custom/patches/v15_9/add_report_project_sites.py` — регистрация Script Report.
- `ferum_custom/patches/v15_9/fix_workspaces_objects_shortcuts_project_sites.py` — нормализация shortcut “Объекты” на report `Project Sites`.

### 3.7 Патчи/миграции legacy → текущая модель
- `ferum_custom/patches/v15_9/backfill_project_sites_from_service_objects.py` — создаёт child‑строки `Project Site` из legacy `Service Object` (вставка напрямую в child‑таблицу, чтобы обойти Project.validate/P0).
- `ferum_custom/patches/v15_9/update_project_p0_custom_field_labels_ru.py` — переименование label `project_sites`.

### 3.8 Audit артефакты (доказательная база скана)
- `docs/audit/project_site_usage_files.txt`
- `docs/audit/project_site_usage_rg.txt`

## 4) Риски перехода (важно учесть до реализации)

1) **Конфликт имени DocType**: `Project Site` уже существует как `istable=1`. TO‑BE требует не‑istable DocType с тем же названием.
2) `Project.project_sites` (Table) **жёстко ожидает child‑DocType**. Если просто поменять `istable` у `Project Site`, Project‑форма и существующие данные сломаются.
3) `Service Request.project_site` сейчас хранит значения `name` child‑строк. При смене модели надо:
   - сохранить обратную совместимость значений,
   - не потерять Drive‑ссылки,
   - обеспечить корректную проверку доступа.
4) Drive‑папки сейчас “проект → объекты”. TO‑BE требует “контракт/сайт → документы/журнал/заявки”, поэтому потребуется staged‑cutover.

## 5) Предлагаемый безопасный путь реализации (высокоуровневый)

Рекомендуемый вариант с минимальным риском и без поломки действующих процессов:

1) Ввести новый самостоятельный DocType `Project Site` (truth).
2) Legacy child DocType переименовать (например, `Project Site Row`) и оставить в `Project.project_sites` как deprecated/read‑only.
3) Написать идемпотентный patch:
   - создать truth‑`Project Site` из legacy rows,
   - (по возможности) сохранить `name` как в legacy row, чтобы `Service Request.project_site` не требовал массового переписывания,
   - заполнить `project/contract` поля truth‑объекта.
4) Обновить валидации/бот/drive/security так, чтобы они читали truth‑`Project Site` (а legacy — только для отображения истории).

Следующие шаги реализации описаны в отдельном плане и будут оформлены в виде патчей + тестов + runbook.
