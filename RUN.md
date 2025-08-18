# Ferum Customizations - Advanced Docker Deployment Guide

This guide outlines the advanced deployment strategy for Ferum Customizations using the `frappe_docker` methodology. This approach provides a robust, production-ready setup with custom image building, modular Docker Compose configurations, and integrated backup solutions.

**Important Note:** This deployment strategy switches the database from PostgreSQL to **MariaDB** for better compatibility with standard Frappe/ERPNext setups and aligns with the provided advanced `docker-compose.yml`.

## Prerequisites

Before you begin, ensure you have the following installed on your server or local machine:

*   **Linux/macOS/Windows (WSL2)**
*   **Docker Engine ≥ 24, Docker Compose v2**
*   **Docker Memory:** ≥ 4 GB
*   **DNS/Domain Access:** (for production HTTPS)
*   **(Optional) `jq`, `base64`, `cron`:** For advanced operations and periodic tasks.

## 1. Prepare Environment Variables (`.env`)

Create a `.env` file in the root directory of your project (`ferum_custom/`) and populate it with the following variables. Replace placeholder values (`your_...`) with your actual secure credentials.

```dotenv
# Versions
FRAPPE_VERSION=version-15
ERPNEXT_VERSION=version-15

# Database
DB_PASSWORD=your_db_password
MYSQL_ROOT_PASSWORD=your_mysql_root_password

# Redis
REDIS_CACHE=redis://redis-cache:6379
REDIS_QUEUE=redis://redis-queue:6379
REDIS_SOCKETIO=redis://redis-queue:6379

# HTTPS (Let's Encrypt)
LETSENCRYPT_EMAIL=your_email@example.com

# Sites
SITES=`erp.ferumrus.ru`

# Custom App
FERUM_CUSTOMS_REPO=https://github.com/your-org/ferum_customs.git
FERUM_CUSTOMS_BRANCH=main

# FastAPI Internal JWT Token (for Frappe to FastAPI calls)
FASTAPI_INTERNAL_JWT_TOKEN=your_fastapi_internal_jwt_token

# Backup Configuration (for backup-job.yml)
RESTIC_REPOSITORY=s3:https://s3.endpoint.com/restic
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
RESTIC_PASSWORD=your_restic_password
PROJECT_NAME=ferum_customs
```

**Important:** Adjust the values for your environment and keep the `.env` file out of version control for security reasons.

## 2. Define Custom App (`apps.json`)

Create an `apps.json` file in the root of your project (`ferum_custom/apps.json`). This file defines the applications to be included in your custom Frappe Docker image.

```json
[
  {"url": "https://github.com/frappe/erpnext", "branch": "version-15"},
  {"url": "https://github.com/your-org/ferum_customs.git", "branch": "main"}
]
```

## 3. Custom Dockerfile

Ensure you have a `Dockerfile` in the root of your project (`ferum_custom/Dockerfile`). This Dockerfile builds your custom Frappe image with the `ferum_customs` app baked in, using the `APPS_JSON_BASE64` build argument.

```dockerfile
FROM frappe/bench:version-15

USER root

# Install git and other necessary tools
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

USER frappe

WORKDIR /home/frappe/frappe-bench

# Build arguments for apps.json
ARG APPS_JSON_BASE64

# Install apps from APPS_JSON_BASE64
# This step will clone and install apps defined in apps.json
# The apps.json is passed as a base64 encoded string
RUN if [ -n "$APPS_JSON_BASE64" ]; then \
    echo "$APPS_JSON_BASE64" | base64 -d > apps.json; \
    bench get-apps-from-json apps.json; \
    bench install-apps-from-json apps.json; \
    rm apps.json; \
fi

# Build assets for all installed apps
RUN bench build

# Set default command to keep container running (bench start will be run via docker exec)
CMD ["sleep", "infinity"]
```

## 4. Modular Docker Compose Configuration

This project uses a modular Docker Compose setup. You will generate the final `docker-compose.yml` by combining base and override files. Ensure these files are present in your project root (or a dedicated `docker/` subdirectory if you prefer to organize them).

*   **`compose.yaml` (Base services):**

    ```yaml
    version: "3.7"

    services:
      backend:
        image: ${FRAPPE_DOCKER_IMAGE:-frappe/erpnext}:${FRAPPE_VERSION:-latest}
        platform: linux/amd64
        command: sleep infinity
        environment:
          - SHELL=/bin/bash
          - DB_HOST=${DB_HOST}
          - DB_PORT=${DB_PORT}
          - REDIS_CACHE=${REDIS_CACHE}
          - REDIS_QUEUE=${REDIS_QUEUE}
          - REDIS_SOCKETIO=${REDIS_SOCKETIO}
          - FRAPPE_SITE_NAME=${SITES}
          - ADMIN_PASSWORD=${ADMIN_PASSWORD}
          - DB_NAME=${DB_NAME}
          - DB_USER=${DB_USER}
          - DB_PASSWORD=${DB_PASSWORD}
        volumes:
          - sites:/home/frappe/frappe-bench/sites
          - logs:/home/frappe/frappe-bench/logs
          # Mount custom app for development if needed
          # - ./ferum_custom:/home/frappe/frappe-bench/apps/ferum_custom
        working_dir: /home/frappe/frappe-bench
        ports:
          - "8000:8000"
        depends_on:
          - db
          - redis-cache
          - redis-queue

      db:
        image: ${DB_IMAGE:-mariadb:10.6}
        platform: linux/amd64
        environment:
          MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
          MYSQL_DATABASE: ${DB_NAME}
          MYSQL_USER: ${DB_USER}
          MYSQL_PASSWORD: ${DB_PASSWORD}
        volumes:
          - db-data:/var/lib/mysql

      redis-cache:
        image: redis:alpine
        platform: linux/amd64
        command: redis-server --appendonly no --requirepass ${REDIS_CACHE_PASSWORD}

      redis-queue:
        image: redis:alpine
        platform: linux/amd64
        command: redis-server --appendonly no --requirepass ${REDIS_QUEUE_PASSWORD}

    volumes:
      sites:
      logs:
      db-data:
    ```

*   **`compose.mariadb.yaml` (MariaDB override):**

    ```yaml
    version: "3.7"

    services:
      db:
        image: docker.io/mariadb:10.6
        platform: linux/amd64
        command:
          - --character-set-server=utf8mb4
          - --collation-server=utf8mb4_unicode_ci
          - --skip-character-set-client-handshake
          - --skip-innodb-read-only-compressed # Temporary fix for MariaDB 10.6
        volumes:
          - mariadb-data:/var/lib/mysql

    volumes:
      mariadb-data:
    ```

*   **`compose.redis.yaml` (Redis override):**

    ```yaml
    version: "3.7"

    services:
      redis-cache:
        image: docker.io/redis:alpine
        platform: linux/amd64
        command: redis-server --appendonly no --requirepass ${REDIS_CACHE_PASSWORD}

      redis-queue:
        image: docker.io/redis:alpine
        platform: linux/amd64
        command: redis-server --appendonly no --requirepass ${REDIS_QUEUE_PASSWORD}
    ```

*   **`compose.https.yaml` (HTTPS with Caddy override):**

    ```yaml
    version: "3.7"

    services:
      caddy:
        image: caddy:2.7.5-alpine
        platform: linux/amd64
        restart: unless-stopped
        ports:
          - "80:80"
          - "443:443"
        volumes:
          - caddy-data:/data
          - caddy-config:/config
          - ./Caddyfile:/etc/caddy/Caddyfile:ro
        environment:
          - LETSENCRYPT_EMAIL=${LETSENCRYPT_EMAIL}
          - SITES=${SITES}
        depends_on:
          - backend

    volumes:
      caddy-data:
      caddy-config:
    ```

*   **`Caddyfile` (for HTTPS):**

    ```caddy
    ${SITES} {
      tls ${LETSENCRYPT_EMAIL}
      reverse_proxy backend:8000
    }
    ```

## 5. Build the Custom Frappe Image

First, encode your `apps.json` to base64:

```bash
export APPS_JSON_BASE64=$(base64 -w 0 apps.json)
```

Then, navigate to the root of your project (`ferum_custom/`) and build your custom Docker image. This process will include the `ferum_customs` app into the image.

```bash
docker build \
  --build-arg APPS_JSON_BASE64=${APPS_JSON_BASE64} \
  -t ferum_customs:version-15 \
  -f Dockerfile .
```

## 6. Generate Final `docker-compose.yml`

Generate the final `docker-compose.yml` by combining the base and override files. This example uses MariaDB, Redis, and HTTPS overrides.

```bash
docker compose -f compose.yaml \
  -f compose.mariadb.yaml \
  -f compose.redis.yaml \
  -f compose.https.yaml \
  config > docker-compose.yml
```

## 7. Running the Project

To start all services:

```bash
docker compose up -d
```

## 8. Create First Site and Install App

After the containers are up, you need to create the Frappe site and install the `ferum_customs` app. Execute these commands inside the `frappe` container:

```bash
docker compose exec backend bench new-site --mariadb-user-host-login-scope=% \
  --db-root-password ${MYSQL_ROOT_PASSWORD} \
  --admin-password ${ADMIN_PASSWORD} \
  ${SITES}

docker compose exec backend bench --site ${SITES} install-app ferum_customs
```

## 9. Updating the Application

To update the application after pushing new code to your repository:

1.  **Rebuild the custom image:**
    ```bash
    export APPS_JSON_BASE64=$(base64 -w 0 apps.json)
    docker build \
      --build-arg APPS_JSON_BASE64=${APPS_JSON_BASE64} \
      -t ferum_customs:version-15 \
      -f Dockerfile .
    ```
2.  **Pull new images and restart services:**
    ```bash
    docker compose pull
    docker compose up -d
    ```
3.  **Run migrations (if necessary):**
    ```bash
    docker compose exec backend bench --site ${SITES} migrate
    ```

## 10. Access the Applications

*   **ERPNext:** Access via your web browser at `https://${SITES}` (if HTTPS is configured) or `http://localhost:8000` (if no proxy). Login with `Administrator` and the `ADMIN_PASSWORD` you set in `.env`.

*   **FastAPI Backend:** The FastAPI backend should be accessible at `http://localhost:8000/api/v1` (or the port you configured). You can test the health check endpoint:
    `http://localhost:8000/api/v1/health`

## 11. Running the Telegram Bot

The Telegram bot runs as a separate Python process. Ensure you have set `TELEGRAM_BOT_TOKEN` in your `.env` file.

Navigate to the `backend` directory (`ferum_custom/backend/`) and run the bot:

```bash
pip install -r requirements.txt # Install bot dependencies
python -m bot.telegram_bot
```

**Note:** Replace `YOUR_FASTAPI_JWT_TOKEN` in `backend/bot/telegram_bot.py` and `ferum_custom/notifications.py` with a valid token for testing.

## 12. Backup Strategy

This project uses a dedicated `backup-job.yml` for periodic backups. Ensure you have configured the backup variables in your `.env` file.

*   **`backup-job.yml`:**

    ```yaml
    version: "3.7"
    services:
      backup:
        image: frappe/erpnext:${FRAPPE_VERSION}
        entrypoint: ["bash", "-c"]
        command: |-
          bench --site all backup
          ## Для restic раскомментируй:
          # restic snapshots || restic init
          # restic backup sites
          ## Хранить только последние 30 снимков:
          # restic forget --group-by=paths --keep-last=30 --prune
        environment:
          - RESTIC_REPOSITORY=${RESTIC_REPOSITORY}
          - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
          - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
          - RESTIC_PASSWORD=${RESTIC_PASSWORD}
        volumes:
          - "sites:/home/frappe/frappe-bench/sites"
        networks:
          - erpnext-network

    networks:
      erpnext-network:
        external: true
        name: ${PROJECT_NAME:-erpnext}_default

    volumes:
      sites:
        external: true
        name: ${PROJECT_NAME:-erpnext}_sites
    ```

*   **Periodic Execution (e.g., every 6 hours via cron):**

    ```cron
    0 */6 * * * docker compose -p erpnext exec backend bench --site all backup --with-files > /dev/null
    ```

    **Notes:**
    *   Ensure `docker compose` is in your `$PATH`.
    *   Adjust the cron interval and project name (`-p erpnext`) as needed.
    *   For Docker Swarm, use `swarm-cronjob`; for Kubernetes, use `CronJob`.

## 13. Daily Routine (Useful Commands)

```bash
# Check availability
curl http://127.0.0.1:8000/api/method/ping

# Bench status (execute inside the frappe container)
docker compose exec backend bash -lc 'bench doctor'

# Force migrations (execute inside the frappe container)
docker compose exec backend bench --site ${SITES} migrate
```

## 14. Stop the Project

To stop all running Docker containers and remove their networks and volumes (optional):

```bash
docker compose down
# To remove volumes (data will be lost!):
docker compose down --volumes
```

## Troubleshooting

*   **Container issues:** Use `docker compose logs <service_name>` to view logs for a specific service (e.g., `docker compose logs frappe`).
*   **Permissions:** Ensure your user has appropriate permissions to run Docker commands.
*   **Environment variables:** Double-check that your `.env` file is correctly configured and located in the project root.

This guide provides a comprehensive overview of deploying Ferum Customizations using the `frappe_docker` methodology. For more detailed information on specific `frappe_docker` features, refer to its official documentation.
