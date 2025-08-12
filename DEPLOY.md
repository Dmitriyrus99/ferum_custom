# Deployment Guide

This project is deployed using Docker Compose. The steps below outline the minimal setup required to bring up the stack on a new host.

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

