# Runtime audit (bench execute)

Цель: быстрый read-only аудит корректности модулей/доктайпов/отчётов/воркспейсов/интеграций одной командой.

## Команды

Запуск на конкретном сайте:

- `bench --site test_site execute ferum_custom.setup.audit.run --kwargs "{'write_report': 1}"`
- `bench --site erpclone.ferumrus.ru execute ferum_custom.setup.audit.run --kwargs "{'write_report': 1}"`

Результат:

- JSON отчёт сохраняется в `apps/ferum_custom/docs/audit/`:
  - `YYYY-MM-DD_runtime_audit_<site>.json`

## Что проверяется

- Импорты активных hook targets (`hooks.py`) — чтобы избежать `ModuleNotFoundError` в рантайме.
- Загрузка meta всех стандартных DocType из модуля `Ferum Custom`.
- Выполнение всех Query Report из модуля `Ferum Custom` с пустыми фильтрами (`filters={}`) — типичная причина 500.
- Workflow → наличие `document_type` (чтобы не было workflow на удалённый DocType).
- Workspace shortcuts для “Объекты” — предупреждает, если ссылка ведёт на legacy routes (`/app/asset`, `/app/service-object`).
- Интеграции через `ferum_custom.api.system_health.status` (без вывода секретов).

Важно:

- Аудит **ничего не изменяет** в БД (read-only).
- Аудит **не выводит секреты** (только “configured=true/false” и безопасные метаданные).
