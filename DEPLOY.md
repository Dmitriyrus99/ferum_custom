## 1. Configure environment

Create a `.env` file in the repository root and fill in the required variables. The example below covers the essential options:

```dotenv
# Versions
BENCH_TAG=v5.25.4
ERP_VERSION=version-15

# Site
SITE_NAME=erp.ferumrus.ru
ADMIN_PASSWORD=changeme

# Database (PostgreSQL example)
DB_TYPE=postgres
POSTGRES_HOST=postgres
POSTGRES_DB=site1
POSTGRES_USER=site1
POSTGRES_PASSWORD=strongpass

# Redis
REDIS_PASSWORD=changeme

# Application source
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

Adjust the values for your environment and keep the file out of version control.

## 2. Start services

Bring up the services and run the one‑time setup helper:

```bash
docker compose up -d postgres redis
docker compose up -d backend
docker compose run --rm setup
# afterwards
docker compose up -d
```

The `setup` service installs the application, applies migrations and can be re‑run safely to update an existing deployment.

## 3. Updating

To pull new code and apply database migrations on an existing instance:

```bash
docker compose run --rm setup
docker compose restart backend
```

For more detailed information and troubleshooting tips see [RUN.md](RUN.md).

