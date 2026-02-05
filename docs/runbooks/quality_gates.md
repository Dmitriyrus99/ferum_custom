# Quality gates (локально + CI)

Цель: чтобы **каждый коммит/PR** проходил одинаковые проверки (pre-commit, линтеры, тесты) и несоответствия исправлялись до отправки в репозиторий.

## 1) Что проверяет CI

GitHub Actions:

- `Quality` (`.github/workflows/linter.yml`)
  - `pre-commit --all-files`
  - `python -m compileall -q telegram_bot`
- `Security` (`.github/workflows/security.yml`)
  - Semgrep rules (frappe/semgrep-rules)
- `CI` (`.github/workflows/ci.yml`)
  - `pytest backend/tests`
  - bench: установка Frappe/ERPNext + `install-app ferum_custom` + `migrate` + `run-tests --app ferum_custom` + `bench build`
- `Mypy (backend)` (в `linter.yml`)

## 2) Быстрый чек перед коммитом (обязательно)

1. Установить pre-commit (1 раз):
   - `pip install pre-commit`
   - `cd apps/ferum_custom && pre-commit install`

Либо (рекомендуется) одной командой из корня репозитория `apps/ferum_custom`:

- `bash scripts/precommit/install.sh`

Важно: первый запуск pre-commit скачивает hook-репозитории (обычно с GitHub). Если на машине нет исходящего доступа в интернет,
запускай эти проверки на dev-машине с доступом или полагайся на CI.

2. Запустить auto-fix + проверку:
   - `pre-commit run --all-files`

Если хук что-то переформатировал — **добавь изменения в stage** и повтори:

- `git add -A && pre-commit run --all-files`

## 3) Если окружение контейнера не даёт писать в `~/.cache`

В некоторых контейнерах `~/.cache` может быть read-only/запрещён. Тогда запускай так:

- `PRE_COMMIT_HOME=/path/to/writable/.cache/pre-commit pre-commit run --all-files`

Рекомендуемая директория (bench):

- `PRE_COMMIT_HOME=/home/frappe/frappe-bench/.cache/pre-commit`

Скрипты в `scripts/precommit/*` сами ставят `PRE_COMMIT_HOME` в `apps/ferum_custom/.cache/pre-commit` (если переменная не задана).

## 4) Полный чек перед пушем (рекомендуется)

Перед `git push` установи pre-push hook (см. ниже). Он запускает:

- `ruff check` (все Python файлы проекта)
- `ruff format --check` (все Python файлы проекта)
- `python -m compileall` (backend/ + ferum_custom/ + telegram_bot/ + scripts/)
- `pytest backend/tests` (если окружение разрешает sockets; иначе тесты пропускаются)
- `mypy` по `backend/`

Чтобы это было автоматом перед `git push`, можно поставить hook:

- `pre-commit install --hook-type pre-push`

Или прогнать pre-push stage вручную:

- `bash scripts/precommit/run_pre_push.sh`

Для Frappe/ERPNext интеграционных тестов ориентируйся на CI:

- `bench --site test_site run-tests --app ferum_custom`

## 5) Правило “исправлять несоответствия в каждом PR”

1. Любое изменение кода → `pre-commit run --all-files` **в этом же PR**.
2. Не “откладывать на потом”:
   - форматирование/импорты → править сразу (ruff/prettier)
   - lint ошибки → устранять сразу
3. Если правка требует массового рефакторинга — выноси в отдельный PR.
