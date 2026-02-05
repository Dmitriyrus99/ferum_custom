### Ferum

Custom

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO
bench install-app ferum_custom
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/ferum_custom
pre-commit install
pre-commit install --hook-type pre-push
```

Or use the helper script:

```bash
bash scripts/precommit/install.sh
```

If you run inside a container where `~/.cache` is read-only, set a writable cache dir:

```bash
export PRE_COMMIT_HOME=/home/frappe/frappe-bench/.cache/pre-commit
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade (via ruff `UP` rules)

Local/CI quality checklist: see `docs/runbooks/quality_gates.md`.

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Runs tests on every push to `main`/`develop` and on pull requests (includes `pip-audit`).
- Linters: Runs `pre-commit` and [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) on pushes and pull requests.
- Deploy: Runs on push to `main` only when secrets are set (`SSH_HOST`, `SSH_USERNAME`, `SSH_KEY`, `DEPLOY_PATH`).

### Telegram bot (aiogram)

Бот запускается отдельным процессом (`frappe-bench-telegram-bot` / `Procfile`) и работает через ERP API (token auth).

Команды (основные):
- `/register <email>` → отправка кода подтверждения на email
- `/projects` → выбрать активный проект
- `/new_request` → создать заявку (Service Request)
- `/my_requests` → список заявок по проекту
- `/attach` → прикрепить фото/файл к заявке (загружает в Google Drive)
- `/survey` → фото/чек-лист обследования (загружает в Google Drive)
- `/subscribe` / `/unsubscribe` → подписки на проект
- `/cancel` → отменить текущий диалог

Настройки (`.env`):
- `FERUM_TELEGRAM_BOT_TOKEN` — токен бота (обяз.)
- `FERUM_TELEGRAM_MODE=webhook|polling`
- `FERUM_TELEGRAM_WEBHOOK_URL` — публичный base URL (обяз. для `webhook`)
- `FERUM_TELEGRAM_WEBHOOK_SECRET` — секретный токен для webhook (рекомендуется)
- `FERUM_FRAPPE_BASE_URL` — base URL ERP (например `https://erpclone.ferumrus.ru`)
- `FERUM_FRAPPE_API_KEY` / `FERUM_FRAPPE_API_SECRET` — ключи API пользователя (обычно System Manager)

Проверка:
- `curl http://127.0.0.1:8080/tg-bot/health`
- В Telegram: `/help`

Security:
- Не допускай появления Telegram bot token в логах. Если токен утёк (traceback/URL) — срочно ротируй через BotFather и обнови `.env`.

### Google Drive (папки проектов)

Интеграция создаёт структуру папок в Google Drive для `ERPNext Project` и объектов (`Project Site`) и сохраняет ссылки:
- `Project.drive_folder_url`
- `Project Site.drive_folder_url`

Требования:
- Включить **Google Drive API** в Google Cloud проекте, которому принадлежит service account JSON.
- Расшарить корневую папку Google Drive на `client_email` service account с правами **Editor**.
- Положить JSON ключ в `sites/<SITE>/private/keys/google_drive_service_account.json` (права `600`).

Настройка (любой из вариантов):
- Через site config:
  - `bench --site <SITE> set-config google_drive_folder_id "<FOLDER_ID>"`
  - `bench --site <SITE> set-config google_drive_service_account_key_path "/abs/path/to/google_drive_service_account.json"`
- Через env (поддерживается также `GOOGLE_DRIVE_FOLDER_ID`, `FERUM_GOOGLE_DRIVE_FOLDER_ID` и `FERUM_GOOGLE_DRIVE_ROOT_FOLDER_ID`):
  - `FERUM_GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_PATH=/abs/path/to/google_drive_service_account.json`
  - `FERUM_GOOGLE_DRIVE_FOLDER_ID=<FOLDER_ID>`

Использование:
- В карточке проекта нажать кнопку **«Создать папки Google Drive»**
- Или вызвать метод `ferum_custom.api.project_drive.ensure_drive_folders` (POST) с параметром `project`.

### License

mit
