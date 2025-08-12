# How to Build and Run Ferum Customizations

This document provides instructions on how to set up and run the Ferum Customizations project, including the ERPNext application, the FastAPI backend, and the Telegram bot.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

*   **Git:** For cloning the repository.
*   **Docker:** [Install Docker Engine](https://docs.docker.com/engine/install/) for your operating system.
*   **Docker Compose:** [Install Docker Compose](https://docs.docker.com/compose/install/) (usually comes with Docker Desktop).
*   **Python 3.10+:** For the FastAPI backend and Telegram bot development.
*   **Node.js (LTS recommended):** For ERPNext frontend asset compilation (if you plan to modify frontend assets).

## 1. Clone the Repository

First, clone the project repository to your local machine:

```bash
git clone <repository_url>
cd ferum_custom
```

## 2. Set up Environment Variables

Create a `.env` file in the root directory of the project (`ferum_custom/`) and populate it with the necessary environment variables. These variables are crucial for database connections, API keys, and other configurations.

Example `.env` content:

```dotenv
# Database Configuration (for MariaDB/PostgreSQL service in Docker Compose)
MYSQL_ROOT_PASSWORD=your_mysql_root_password
MYSQL_DATABASE=ferum_erpnext_db
MYSQL_USER=ferum_user
MYSQL_PASSWORD=ferum_db_password

# ERPNext API Credentials (for FastAPI backend to connect to ERPNext)
ERP_API_URL=http://erpnext:8000 # This is the internal Docker network address
ERP_API_KEY=your_erpnext_api_key
ERP_API_SECRET=your_erpnext_api_secret

# FastAPI Backend Configuration
SECRET_KEY=your_fastapi_secret_key # Used for JWT token signing

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Sentry DSN (for error tracking)
SENTRY_DSN=your_sentry_dsn # Optional: leave empty if not using Sentry
```

**Important:** Replace placeholder values (`your_...`) with your actual secure credentials. Do not commit this file to version control.

## 3. Build and Run Docker Containers

The project uses Docker Compose to orchestrate the ERPNext, database, Redis, and FastAPI backend services. You will need to build the custom Docker images and start the services.

Navigate to the project root directory (`ferum_custom/`) where your `docker-compose.yml` (or similar) file is located. If you don't have a `docker-compose.yml` yet, you'll need to create one based on the example provided in `backend/staging_notes.md` or the project's deployment documentation.

```bash
docker-compose build
docker-compose up -d
```

This command will:
*   Build the Docker images for your services (ERPNext app with `ferum_custom` installed, FastAPI backend).
*   Start all defined services in detached mode (`-d`).

## 4. Set up ERPNext Site and App

After the containers are running, you need to set up the ERPNext site and install the `ferum_custom` app within the ERPNext container. You can access the ERPNext container's bash shell to run `bench` commands.

First, find the name of your ERPNext container:

```bash
docker ps
```

Look for a container name similar to `ferum_custom_erpnext_1` or `erpnext_app_1`. Let's assume it's `ferum_custom_erpnext_1`.

Now, execute commands inside the container:

```bash
docker exec -it ferum_custom_erpnext_1 bash
```

Once inside the container's bash shell, navigate to the `frappe-bench` directory (usually `/home/frappe/frappe-bench`) and run the following `bench` commands:

```bash
# Create a new ERPNext site
bench new-site erp.ferumrus.ru --db-root-password your_mysql_root_password --admin-password your_erpnext_admin_password

# Install the custom app on the new site
bench --site erp.ferumrus.ru install-app ferum_custom

# Run migrations (important after installing/updating apps)
bench --site erp.ferumrus.ru migrate

# Build frontend assets (if you made changes to JS/CSS)
bench build

# Exit the container shell
exit
```

**Note:** Replace `your_mysql_root_password` and `your_erpnext_admin_password` with the values you set in your `.env` file.

## 5. Access the Applications

*   **ERPNext:** Once the ERPNext site is set up, you can access it via your web browser. By default, if Nginx is configured to expose port 80/443, it might be accessible at `http://localhost` or `https://localhost` (if SSL is set up). You might need to check your `docker-compose.yml` and Nginx configuration for the exact port mapping.
    *   Login with `Administrator` and the `your_erpnext_admin_password` you set.

*   **FastAPI Backend:** The FastAPI backend should be accessible at `http://localhost:8001` (or the port you configured in `docker-compose.yml`). You can test the health check endpoint:
    `http://localhost:8001/api/v1/health`

## 6. Run the Telegram Bot

The Telegram bot runs as a separate Python process. Ensure you have set `TELEGRAM_BOT_TOKEN` in your `.env` file.

Navigate to the `backend` directory (`ferum_custom/backend/`) and run the bot:

```bash
pip install -r requirements.txt # Install bot dependencies
python -m bot.telegram_bot
```

## 7. Run Backend Tests

To run the FastAPI backend tests, first install the backend as an editable package from the project root:

```bash
pip install -e ./backend
pytest -q ./backend/tests
```

## 8. Stop the Project

To stop all running Docker containers and remove their networks and volumes (optional):

```bash
docker-compose down
# To remove volumes (data will be lost!):
docker-compose down --volumes
```

## Troubleshooting

*   **Container issues:** Use `docker-compose logs <service_name>` to view logs for a specific service (e.g., `docker-compose logs erpnext`).
*   **Permissions:** Ensure your user has appropriate permissions to run Docker commands.
*   **Environment variables:** Double-check that your `.env` file is correctly configured and located in the project root.

This guide should help you get the Ferum Customizations project up and running. For detailed development and configuration, refer to the `docs/` directory and individual module documentation.