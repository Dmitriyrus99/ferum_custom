# Управление договором и проектом (Contract → Project)

Дата: 2026‑02‑10  
Контур: ERPNext/Frappe v15 + `ferum_custom`.

Цель процесса: сделать **`Contract` источником договорных данных**, а **`Project` — управленческим контейнером** (1:1 для активных договоров).

## Участники и зоны ответственности

- **Project Manager / Projects Manager** — заводит/ведёт договор, задаёт PM на контракте/проекте, управляет объектами/заявками.
- **Office Manager** — помогает с документооборотом, Drive‑структурой и регистрацией клиента/контактов.
- **System Manager / Administrator** — настройки, миграции, интеграции (Drive/Vault/бот).

## AS‑IS: как это реализовано в системе

### Шаги процесса

1) Создать/обновить `Contract` (ERPNext).
2) Убедиться, что контрагент — **Customer**:
   - `Contract.party_type == "Customer"`
   - `Contract.party_name` существует в `Customer`
3) Перевести договор в статус `Active`.
4) Система автоматически обеспечит связь 1:1:
   - найдёт существующий `Project` по `Project.contract`
   - либо создаст новый `Project`
   - синхронизирует ключевые поля `Customer/Company/PM/expected_*`

Код: `ferum_custom/services/contract_project_sync.py` (hooks см. `ferum_custom/hooks.py`).

### Контроль целостности (инварианты)

- Для активного договора допустим **ровно один** проект:
  - валидируется в `validate_project_unique_contract`
- Для `Project.project_type == "External"` связь с `Contract` обязательна:
  - валидируется в `validate_project_has_contract`

## Связанные подпроцессы

### P0‑цикл проекта (опционально)

Если на проекте включён `Project.ferum_p0_enabled=1`, то на `Project.validate` включаются гейты стадий и дедлайны,
а daily scheduler шлёт эскалации (email/telegram best‑effort).

- гейты: `ferum_custom/services/project_full_cycle.py`
- эскалации: `ferum_custom/services/project_escalations.py`

### Google Drive структура для проекта

Drive‑папки проекта создаются детерминированно и сохраняются в `Project.drive_folder_url`.
Дальше по объектам создаются подпапки (см. runbook Drive‑структуры).

- API: `ferum_custom/api/project_drive.py`
- runbook: `docs/runbooks/google_drive_structure.md`

## Legacy (важно)

В репозитории присутствуют `Service Project` / `Service Object` как исторический контур.
Новые процессы опираются на `Contract` + `Project` + `Project Site` (truth).
