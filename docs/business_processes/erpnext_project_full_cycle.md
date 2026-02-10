# Контракт/проект: полный цикл (Project как контейнер, Project Site как “истина”)

Дата: 2026‑02‑10  
Контур: ERPNext/Frappe v15 + кастомное приложение `ferum_custom`.

Документ описывает **верхнеуровневый бизнес‑процесс “от договора до закрытия”** в текущей архитектуре Ferum ERP, с фиксацией:

- где хранится “истина” (операционные и доказательные данные);
- какие автоматизации уже реализованы в коде;
- какие части ещё остаются legacy и требуют миграции.

См. также:

- “Project как контейнер”: `docs/architecture/project_as_container.md`
- модель объектов обслуживания: `docs/architecture/project_site_tobe.md`
- AS‑IS процессы по шагам: `docs/business_processes/business_processes_ru.md`

---

## 1) Сущности и роли (в контексте полного цикла)

**Сущности:**

- `Contract` — договор с заказчиком (источник управленческой привязки).
- `Project` — контейнер: membership/аналитика/Drive‑папка проекта/связь с Contract.
- `Project Site` — объект обслуживания (адрес/инженер/SLA/Drive‑папки объекта, журнал).
- `Service Request` — заявка/инцидент/регламент по объекту.
- `Service Report` — отчёт о выполнении работ, закрывает заявку при submit.
- `Service Logbook` / `Service Log Entry` — журнал эксплуатации (электронный + учёт бумажного).
- `ServiceAct` / `ActSchedule` / `Invoice` — актирование и финансы.
- `File` — документы и вложения (включая Drive‑first “Документы проекта”).

**Роли (минимум):**

- PM/Projects Manager — управляет договором/контейнером Project, контролирует заявки и документы.
- Office Manager — документооборот (письма/сканы/закрывающие).
- Engineer — выполнение заявок по объектам (Desk/Telegram).
- Client — ограниченный доступ к своему контуру (проекты/документы/статусы).

---

## 2) Цепочка процессов (как работает “полный цикл”)

```mermaid
flowchart LR
    A[Contract (Customer)] --> B[Project (container)]
    B --> C[Project Site (object of service)]
    C --> D[Survey / Evidence (Drive)]
    C --> E[Service Request]
    E --> F[Service Report]
    F --> G[ServiceAct / Invoice]
    G --> H[Payment / Closing]
```

Ключевое архитектурное правило: **операционная “истина” живёт на уровне Project Site и связанных документов**, а `Project` используется как контейнер/связка с `Contract`.

---

## 3) AS‑IS по коду: что уже реализовано

### 3.1 Contract → Project (синхронизация 1:1)

При изменениях `Contract` система обеспечивает наличие связанного `Project` (если на сайте включены соответствующие поля):

- хуки: `ferum_custom/hooks.py` (`Contract.validate`, `Contract.on_update`)
- логика: `ferum_custom/services/contract_project_sync.py`

### 3.2 Project Site как основной объект обслуживания (truth model)

В системе поддержаны две модели (для обратной совместимости):

- `Project Site` (truth, `istable=0`) — основной объект.
- `Project Site Row` (legacy child table, `istable=1`) — исторические строки в `Project.project_sites`.

Миграции/ремонт связей выполняются патчами (идемпотентно), см. `ferum_custom/patches/*project_site*`.

### 3.3 Google Drive (папки проекта и объектов)

Создание/проверка структуры Drive выполняется идемпотентно:

- API/функции: `ferum_custom/api/project_drive.py` (`ensure_drive_folders`)
- правила именования/пути: `docs/runbooks/google_drive_structure.md`

### 3.4 “Документы проекта” (Drive‑first)

Юридически значимые документы проекта загружаются в Drive и фиксируются как `File` с метаданными:

- API: `ferum_custom/api/project_documents.py`
- обязательные поля `File`: `ferum_doc_title`, `ferum_doc_type`, `ferum_drive_file_id`
- ограничения Client по типам: `ferum_custom/services/project_documents_config.py`
- права доступа к `File`: `ferum_custom/security/file_permissions.py`

### 3.5 Заявки и отчёты

- `Service Request` привязывается к `Project Site` (+ legacy `service_object`) и фиксирует источник/время обращения.
  - код: `ferum_custom/ferum_custom/doctype/service_request/service_request.py`
- `Service Report` на submit закрывает заявку и участвует в уведомлениях.
  - код: `ferum_custom/ferum_custom/doctype/service_report/service_report.py`
- уведомления: `ferum_custom/notifications.py`

### 3.6 Финансы (акты/счета)

Контур актирования/счетов реализован через кастомные DocType:

- `ServiceAct`, `ActSchedule`, `Invoice` (см. `ferum_custom/ferum_custom/doctype/*` и `ferum_custom/services/acts.py`)

### 3.7 Legacy‑контур регламента

Генерация регламентных заявок в текущей реализации ещё опирается на legacy `service_object`:

- scheduler: `ferum_custom/services/service_schedule.py` (вызов из `hooks.py`)

---

## 4) TO‑BE принцип хранения “истины” (без breaking changes)

### 4.1 Project (container)

`Project` должен хранить только контейнерные данные, которые полезны для управления и аналитики:

- ссылка на `Contract` (1:1 для активных договоров),
- company/customer,
- membership (PM + `Project.users`),
- ссылка на Drive‑папку проекта (`drive_folder_url`) как корень структуры.

### 4.2 Project Site (операционная истина)

`Project Site` хранит то, что реально требуется для эксплуатации объекта:

- адрес/название,
- назначение инженеров/доступ,
- SLA/окна работ,
- Drive‑папки объекта и разделов (заявки/обследование/документы),
- журнал эксплуатации (электронный + учёт бумажного).

### 4.3 Service Request / Report (операционный цикл)

Заявка и отчёт фиксируют:

- “момент обращения” и “момент регистрации” (для SLA и аудита),
- канал источника (Desk/Bot/Email/Phone/…),
- доказательства/вложения (Drive‑links / File).

---

## 5) Автоматизации и контроль качества

### 5.1 P0‑контур по Project (опционально, feature‑flag)

В `ferum_custom` присутствует P0‑контур “гейтов/эскалаций” по `Project`:

- validate gates: `ferum_custom/services/project_full_cycle.py`
- initial todos: `ferum_custom/services/project_full_cycle.py`
- daily escalations: `ferum_custom/services/project_escalations.py`

Активность контролируется флагом `ferum_p0_enabled` (см. архитектурное описание в `docs/architecture/project_as_container.md`).

### 5.2 Runtime audit и health‑checks

- runtime audit: `ferum_custom/setup/audit.py` (импорты hooks, reports, workflows, workspace shortcuts)
- system health summary: `ferum_custom/api/system_health.py` (wkhtmltopdf/telegram/fastapi/vault/drive + security validation)

---

## 6) Что считается “готовым” полным циклом (критерии)

Минимальные критерии завершённости (без учёта расширений P2):

1) Для каждого активного `Contract` существует связанный `Project` (контейнер).
2) Для каждого объекта обслуживания создан `Project Site` (truth) и привязан к `Project`.
3) Любая новая заявка создаётся с заполненным `project_site` (и не использует `service_object` как первичный ключ).
4) Drive‑структура создаётся идемпотентно и ссылки (`drive_folder_url`) корректно заполнены.
5) Юридические документы ведутся через “Документы проекта” (Drive‑first + метаданные + права).
6) Runtime audit проходит без P0 ошибок (hooks imports, query reports, workflows).

---

## 7) Rollback / backward compatibility

- legacy DocType (`Service Project`, `Service Object`, `Project Site Row`) не удаляются сразу;
- миграции выполняются идемпотентно и оставляют исходные данные на месте;
- откат логики возможен через feature‑flags/отключение новых UI‑маршрутов без потери данных.
