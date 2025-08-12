## Staging Environment Setup Notes

A staging environment is crucial for testing new features and changes before deploying them to production. It should mimic the production environment as closely as possible.

**Key Considerations:**

1.  **Infrastructure:**
    *   Provision a separate server or set of servers (physical or virtual) for staging.
    *   Ensure it has similar specifications (CPU, RAM, storage) to your production environment.
    *   Install Docker and Docker Compose, just like in production.

2.  **Database:**
    *   Set up a separate database instance (MariaDB/PostgreSQL) for staging.
    *   Consider periodically refreshing the staging database with a sanitized copy of production data to ensure realistic testing.

3.  **Configuration:**
    *   Maintain a separate `.env` file or configuration management system for staging-specific settings (e.g., ERPNext API URL, Google API keys, Sentry DSN, Telegram Bot Token).
    *   Ensure all sensitive information is securely managed.

4.  **Deployment Pipeline:**
    *   Extend your GitHub Actions workflow (or other CI/CD tool) to include a deployment step to the staging environment.
    *   This typically involves building Docker images, pushing them to a container registry, and then deploying them to the staging server (e.g., via SSH and `docker-compose pull`/`up`).

5.  **Monitoring:**
    *   Set up monitoring (Prometheus, Sentry) for the staging environment as well, but with separate instances or configurations to avoid mixing data with production.

6.  **Access Control:**
    *   Restrict access to the staging environment to authorized personnel only.

7.  **Testing:**
    *   Perform thorough testing (unit, integration, E2E, user acceptance testing) on the staging environment before promoting changes to production.

**Example `docker-compose.yml` for Staging (similar to production but with staging-specific configurations):**

```yaml
version: '3.8'

services:
  erpnext:
    image: frappe/erpnext:v15.0.0
    environment:
      FRAPPE_SITE_NAME: erp.ferumrus.ru
      DB_HOST: db
      REDIS_CACHE: redis_cache:6379
      REDIS_QUEUE: redis_queue:6379
      # Add other ERPNext specific environment variables
    volumes:
      - erpnext_data:/home/frappe/frappe-bench/sites
      - ./ferum_custom:/home/frappe/frappe-bench/apps/ferum_custom
    depends_on:
      - db
      - redis_cache
      - redis_queue

  backend:
    build: ./backend
    environment:
      ERP_API_URL: http://erpnext:8000 # Link to ERPNext service within Docker network
      SECRET_KEY: ${SECRET_KEY}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      SENTRY_DSN: ${SENTRY_DSN}
      # Add other backend specific environment variables
    ports:
      - "8001:8000" # Expose backend on a different port for staging
    depends_on:
      - erpnext

  db:
    image: mariadb:10.6
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - db_data:/var/lib/mysql

  redis_cache:
    image: redis:alpine

  redis_queue:
    image: redis:alpine

  nginx:
    image: nginx:latest
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - erpnext
      - backend

volumes:
  erpnext_data:
  db_data:
```

This `docker-compose.yml` is a simplified example. You would need to adapt it to your specific needs, including proper volume management, network configuration, and environment variables.