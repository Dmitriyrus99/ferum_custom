#!/bin/bash

# Database restore script

# --- Configuration ---
DB_NAME="your_db_name" # Replace with your PostgreSQL database name
DB_USER="your_db_user" # Replace with your PostgreSQL database user
DB_HOST="localhost"    # Replace with your PostgreSQL database host
DB_PORT="5432"         # Replace with your PostgreSQL database port

BACKUP_DIR="$(pwd)/backups" # Directory where backups are stored locally

# Google Drive configuration (requires gdrive CLI tool or similar)
# GOOGLE_DRIVE_FOLDER_ID="your_google_drive_folder_id" # Replace with your Google Drive folder ID

# --- Function to get the latest backup file ---
get_latest_backup() {
    # For now, assumes latest backup is the most recently modified .sql file in BACKUP_DIR
    # In a real scenario, you might download from Google Drive first
    find "${BACKUP_DIR}" -type f -name "*.sql" -printf "%T@ %p\n" | sort -n | tail -1 | awk '{print $2}'
}

# --- Main restore logic ---
LATEST_BACKUP=$(get_latest_backup)

if [ -z "${LATEST_BACKUP}" ]; then
    echo "Error: No backup files found in ${BACKUP_DIR}. Please ensure backups are present or download from Google Drive."
    # --- Download from Google Drive (Placeholder) ---
    echo "Attempting to download latest backup from Google Drive... (Requires gdrive CLI tool configured)"
    # Example using gdrive CLI to list and download latest:
    # gdrive list --query "'${GOOGLE_DRIVE_FOLDER_ID}' in parents and name contains 'erpnext_backup_'" --order "modifiedTime desc" --limit 1
    # gdrive download <file_id>
    exit 1
fi

echo "Restoring database from: ${LATEST_BACKUP}"

# --- Drop existing database and create a new one (DANGER: This will delete all current data!) ---
# PGPASSWORD="your_db_password" dropdb -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} ${DB_NAME}
# PGPASSWORD="your_db_password" createdb -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} ${DB_NAME}

# --- Restore database from backup ---
PGPASSWORD="your_db_password" psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} < "${LATEST_BACKUP}"

if [ $? -eq 0 ]; then
    echo "Database restored successfully from ${LATEST_BACKUP}"
else
    echo "Error: Database restore failed."
    echo "Please ensure the database exists and the user has appropriate permissions."
fi
