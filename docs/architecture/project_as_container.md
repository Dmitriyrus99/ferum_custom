# TO‑BE: `Project` как «тонкий контейнер» (не источник истины)

Дата: 2026‑02‑10

## 1) Решение

В целевой модели Ferum:

- `Project` используется как **контейнер/связка** (участники, менеджер, аналитика, связь с `Contract`).
- Операционная и доказательная «истина» переносится на уровень `Project Site` и связанных сущностей (`Service Request/Report/Logbook/File/Drive`).

Следствие: любые автоматизации, которые трактуют `Project` как источник фактов (SLA, гейты стадий, эксплуатационные события), должны быть:

- выключены по умолчанию,
- либо переведены на feature‑flag,
- либо перенесены на `Project Site`.

## 2) AS‑IS: где `Project` сейчас используется как «истина»

### 2.1 P0 процесс (stage gates + дедлайны + эскалации)

Активные точки:
- `ferum_custom/services/project_full_cycle.py`
  - `validate_project_p0_stage_gates()` (вызов через `hooks.py` на `Project.validate`)
  - авто‑продвижение стадии и обязательные проверки полей
- `ferum_custom/services/project_escalations.py`
  - `run_daily_project_escalations()` (scheduler daily)
- `ferum_custom/api/project_p0.py`
  - отправка welcome‑email и фиксация полей на `Project`
- `ferum_custom/hooks.py`
  - `doc_events["Project"].validate` включает `validate_project_p0_stage_gates`
  - `scheduler_events.daily` включает `run_daily_project_escalations`

Текущая защита от внезапных блокировок уже есть: `validate_project_p0_stage_gates()` работает только если `ferum_p0_enabled == 1`.

### 2.2 Патчи/кастом‑поля P0

Ветка патчей `ferum_custom/patches/v15_9/*` создаёт и поддерживает P0 поля/скрипты/Workflow:
- `add_project_full_cycle_p0.py`
- `add_project_workflow_p0.py`
- `add_project_p0_settings_fields.py`
- `add_project_client_script_p0.py`
- `update_project_client_script_p0_buttons.py`
- `add_project_p0_enabled_flag.py`
- `disable_p0_for_incomplete_projects.py`
- `hide_unused_project_fields_p0.py`
- и др.

## 3) TO‑BE: что сохраняем, что депрекейт

### 3.1 Что оставляем в `Project`
Минимально необходимые поля/функции:
- связь с `Contract` (1:1)
- membership (Project.users) для разграничения доступа
- `project_manager`, `company`, `customer` (если используется для аналитики/портала)

### 3.2 Что объявляем не‑истиной
- `ferum_stage` и связанные дедлайны/чек‑листы/скрипты — могут оставаться в UI, но не должны влиять на эксплуатационные процессы.

## 4) План безопасного отключения (backward compatible)

1) Сохранить все поля/Workflow/Client Script (ничего не удалять).
2) Сделать так, чтобы в новых установках и в staging:
   - `ferum_p0_enabled` по умолчанию был `0` для всех проектов,
   - scheduler‑эскалации выполнялись только для явно включённых проектов.
3) Перенести эксплуатационные дедлайны/SLA на `Project Site` (в рамках Project Site truth модели).

## 5) Артефакты аудита

- `docs/audit/project_p0_usage_rg.txt` — места использования `ferum_stage/ferum_p0_enabled/project_full_cycle/project_escalations`.
