## How to Build and Run Ferum Customizations (Battle-Tested Docker Deployment)

This document provides a comprehensive guide on how to set up and run the Ferum Customizations project using Docker Compose, ensuring automatic application setup, updates, and migrations.

### 1. Prepare Environment Variables (.env)

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
```

**Note:** If your repository is private, refer to section 5 for authentication options (token in URL or SSH key).

### 2. Basic docker-compose.yml

This is a simplified development variant with one backend container (Bench), plus Postgres and Redis. For production, you would typically add separate workers (scheduler, queue-*) and a reverse proxy.

Create a `docker-compose.yml` file in the project root (`ferum_custom/`) with the following content:

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

volumes:
  bench-vol:
  pgdata:
```

### 3. One-time "setup" service for automatic app installation and migrations

Add the following `setup` service to your `docker-compose.yml`. This service will run once during `docker compose up`, pull your application repository, install the app on the ERPNext site, and run migrations. It is idempotent, meaning repeated runs will not cause issues.

```yaml
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
```

**How it works:**
*   The `setup` service uses the same `bench-vol` volume as the `backend` service, so everything it downloads/installs will be visible to the `backend`.
*   On the first run, it creates the site, then performs `get-app`, `install-app`, and `migrate`.
*   On subsequent deployments, `setup` performs a `git pull` and `migrate` again.

### 4. Running the Project

To start the services and run the setup:

```bash
docker compose up -d postgres redis
docker compose up -d backend
docker compose run --rm setup
# Afterwards, for regular operation:
docker compose up -d
```

### 5. Updating the Application (Git/CI)

To update the application after pushing changes to your repository, simply restart the `setup` service:

```bash
docker compose run --rm setup
docker compose restart backend
```

### 6. Access the Applications

*   **ERPNext:** Access via your web browser at `http://localhost:8000` (or the port configured in your `docker-compose.yml`). Login with `Administrator` and the `ADMIN_PASSWORD` you set in `.env`.

*   **FastAPI Backend:** The FastAPI backend should be accessible at `http://localhost:8000/api/v1` (or the port you configured). You can test the health check endpoint:
    `http://localhost:8000/api/v1/health`

### 7. Running the Telegram Bot

The Telegram bot runs as a separate Python process. Ensure you have set `TELEGRAM_BOT_TOKEN` in your `.env` file.

Navigate to the `backend` directory (`ferum_custom/backend/`) and run the bot:

```bash
pip install -r requirements.txt # Install bot dependencies
python -m bot.telegram_bot
```

**Note:** Replace `YOUR_FASTAPI_JWT_TOKEN` in `backend/bot/telegram_bot.py` with a valid token for testing.

### 8. How to Pull a Private Repository

Choose one method:

**A. Via Token in URL (simpler)**

Set `FERUM_CUSTOMS_REPO` in your `.env` like this:

```dotenv
FERUM_CUSTOMS_REPO=https://<GITHUB_TOKEN>@github.com/your-org/ferum_customs.git
```

The token should have `repo:read` permissions. Do not store it in Git – put it in `.env` or CI secrets.

**B. Via SSH Key (more secure)**

Generate a deploy key (read-only) and add it to your repository settings (`repo → Settings → Deploy keys`).

Mount the key into the container and set `GIT_SSH_COMMAND` in your `docker-compose.yml` for the `setup` service:

```yaml
  setup:
    volumes:
      - bench-vol:/home/frappe/frappe-bench
      - ./deploy_keys/id_ed25519:/home/frappe/.ssh/id_ed25519:ro
      - ./deploy_keys/known_hosts:/home/frappe/.ssh/known_hosts:ro
    environment:
      GIT_SSH_COMMAND: "ssh -i /home/frappe/.ssh/id_ed25519 -o UserKnownHostsFile=/home/frappe/.ssh/known_hosts"
```

And change `FERUM_CUSTOMS_REPO` in your `.env` to the SSH URL:

```dotenv
FERUM_CUSTOMS_REPO=git@github.com:your-org/ferum_customs.git
```

### 9. Daily Routine (Useful Commands)

```bash
# Check availability
curl http://127.0.0.1:8000/api/method/ping

# Bench status
docker compose exec -u frappe backend bash -lc 'bench doctor'

# Force migrations
docker compose exec -u frappe backend bash -lc 'bench --site ${SITE_NAME} migrate'

# Update only your app
docker compose exec -u frappe backend bash -lc '
  cd apps/ferum_customs && git fetch --all && git pull && cd - && bench build && bench --site ${SITE_NAME} migrate
'
```

### 10. Stop the Project

To stop all running Docker containers and remove their networks and volumes (optional):

```bash
docker compose down
# To remove volumes (data will be lost!):
docker compose down --volumes
```

## Troubleshooting

*   **Container issues:** Use `docker-compose logs <service_name>` to view logs for a specific service (e.g., `docker-compose logs erpnext`).
*   **Permissions:** Ensure your user has appropriate permissions to run Docker commands.
*   **Environment variables:** Double-check that your `.env` file is correctly configured and located in the project root.

This guide should help you get the Ferum Customizations project up and running. For detailed development and configuration, refer to the `docs/` directory and individual module documentation.
