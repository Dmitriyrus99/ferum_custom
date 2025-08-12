# Ferum Customizations - Deployment Guide

This guide provides step-by-step instructions to deploy the Ferum Customizations project using Docker Compose. It covers setting up the environment, running the application, and basic management.

## Prerequisites

Before you begin, ensure you have the following installed on your server or local machine:

*   **Docker:** [Install Docker Engine](https://docs.docker.com/engine/install/)
*   **Docker Compose:** [Install Docker Compose](https://docs.docker.com/compose/install/)

## 1. Prepare Environment Variables (.env)

Create a `.env` file in the root directory of your project (`ferum_custom/`) and populate it with the following variables. Replace placeholder values (`your_...`) with your actual secure credentials.

```dotenv
# versions
BENCH_TAG=v5.25.4
ERP_VERSION=version-15

# site
SITE_NAME=erp.ferumrus.ru
ADMIN_PASSWORD=changeme

# DB (example with PostgreSQL)
DB_TYPE=postgres
POSTGRES_HOST=postgres
POSTGRES_DB=site1
POSTGRES_USER=site1
POSTGRES_PASSWORD=strongpass

# Redis
REDIS_PASSWORD=changeme

# your app repository
FERUM_CUSTOMS_REPO=https://github.com/your-org/ferum_customs.git
FERUM_CUSTOMS_BRANCH=main

# Google Drive Integration
# Path to your Google Drive service account JSON key file (relative to site_path/private/keys/)
# Example: google_drive_service_account.json
GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_FILENAME=google_drive_service_account.json
# ID of the Google Drive folder where attachments will be stored
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id

# FastAPI Internal JWT Token (for Frappe to FastAPI calls)
FASTAPI_INTERNAL_JWT_TOKEN=your_fastapi_internal_jwt_token
```

**Important:** Adjust the values for your environment and keep the `.env` file out of version control for security reasons.

## 2. Setup docker-compose.yml

Create a `docker-compose.yml` file in the project root (`ferum_custom/`) with the following content. This configuration includes the ERPNext backend, PostgreSQL database, Redis, and a one-time `setup` service to automate application installation and migrations.

```yaml
services:
  backend:
    image: frappe/bench:${BENCH_TAG}
    container_name: frappe
    env_file: .env
    working_dir: /home/frappe/frappe-bench
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    volumes:
      - bench-vol:/home/frappe/frappe-bench
    command: >
      bash -lc "
      bench start
      "

  postgres:
    image: postgres:13
    env_file: .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]

  setup:
    image: frappe/bench:${BENCH_TAG}
    container_name: frappe-setup
    env_file: .env
    working_dir: /home/frappe/frappe-bench
    depends_on:
      - backend
    volumes:
      - bench-vol:/home/frappe/frappe-bench
    entrypoint: [ "bash", "-lc" ]
    command: |
      '
      set -e

      # 1) Create site if it doesn't exist (PostgreSQL)
      if ! bench --site ${SITE_NAME} whoami >/dev/null 2>&1; then
        echo "[setup] Creating site ${SITE_NAME}..."
        bench new-site ${SITE_NAME} \
          --db-type ${DB_TYPE} \
          --db-host ${POSTGRES_HOST} \
          --db-name ${POSTGRES_DB} \
          --db-user ${POSTGRES_USER} \
          --db-password ${POSTGRES_PASSWORD} \
          --admin-password ${ADMIN_PASSWORD} \
          --no-mariadb-socket
      else
        echo "[setup] Site ${SITE_NAME} already exists."
      fi

      # 2) If the app is not yet downloaded - bench get-app
      if [ ! -d apps/ferum_customs ]; then
        echo "[setup] bench get-app ferum_customs..."
        bench get-app ferum_customs ${FERUM_CUSTOMS_REPO} --branch ${FERUM_CUSTOMS_BRANCH}
      else
        echo "[setup] App ferum_customs already present. Updating..."
        cd apps/ferum_customs && git fetch --all && git checkout ${FERUM_CUSTOMS_BRANCH} && git pull || true
        cd - >/dev/null
      fi

      # 3) Install the app on the site (if not already installed)
      if ! bench --site ${SITE_NAME} list-apps | grep -q "^ferum_customs$"; then
        echo "[setup] Install app on site..."
        bench --site ${SITE_NAME} install-app ferum_customs
      else
        echo "[setup] App already installed on ${SITE_NAME}."
      fi

      # 4) Run migrations
      bench --site ${SITE_NAME} migrate

      echo "[setup] Done."
      '
    restart: "no"

volumes:
  bench-vol:
  pgdata:
```

## 3. Running the Project

To start all services and run the one-time setup:

```bash
docker compose up -d postgres redis
docker compose up -d backend
docker compose run --rm setup
# Afterwards, for regular operation:
docker compose up -d
```

## 4. Updating the Application

After pushing new code to your repository, update an existing deployment by restarting the `setup` service:

```bash
docker compose run --rm setup
docker compose restart backend
```

## 5. Access the Applications

*   **ERPNext:** Access via your web browser at `http://localhost:8000` (or the port configured in your `docker-compose.yml`). Login with `Administrator` and the `ADMIN_PASSWORD` you set in `.env`.

*   **FastAPI Backend:** The FastAPI backend should be accessible at `http://localhost:8000/api/v1` (or the port you configured). You can test the health check endpoint:
    `http://localhost:8000/api/v1/health`

## 6. Running the Telegram Bot

The Telegram bot runs as a separate Python process. Ensure you have set `TELEGRAM_BOT_TOKEN` in your `.env` file.

Navigate to the `backend` directory (`ferum_custom/backend/`) and run the bot:

```bash
pip install -r requirements.txt # Install bot dependencies
python -m bot.telegram_bot
```

**Note:** Replace `YOUR_FASTAPI_JWT_TOKEN` in `backend/bot/telegram_bot.py` and `ferum_custom/notifications.py` with a valid token for testing.

## 7. Troubleshooting

*   **Container issues:** Use `docker-compose logs <service_name>` to view logs for a specific service (e.g., `docker-compose logs backend`).
*   **Permissions:** Ensure your user has appropriate permissions to run Docker commands.
*   **Environment variables:** Double-check that your `.env` file is correctly configured and located in the project root.

This guide should help you get the Ferum Customizations project up and running. For detailed development and configuration, refer to the `docs/` directory and individual module documentation.
