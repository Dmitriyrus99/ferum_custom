#!/bin/bash

# Database backup script

# --- Configuration ---
DB_NAME="your_db_name" # Replace with your PostgreSQL database name
DB_USER="your_db_user" # Replace with your PostgreSQL database user
DB_HOST="localhost"    # Replace with your PostgreSQL database host
DB_PORT="5432"         # Replace with your PostgreSQL database port

BACKUP_DIR="$(pwd)/backups" # Directory to store backups locally
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/erpnext_backup_${TIMESTAMP}.sql"

# Google Drive configuration (requires gdrive CLI tool or similar)
# GOOGLE_DRIVE_FOLDER_ID="your_google_drive_folder_id" # Replace with your Google Drive folder ID

# --- Create backup directory if it doesn't exist ---
mkdir -p "${BACKUP_DIR}"

# --- Perform PostgreSQL database dump ---
PGPASSWORD="your_db_password" pg_dump -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} > "${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    echo "Database backup created successfully: ${BACKUP_FILE}"
    
    # --- Upload to Google Drive (Placeholder) ---
    echo "Uploading backup to Google Drive... (Requires gdrive CLI tool configured)"
    # Example using gdrive CLI:
    # gdrive upload --parent ${GOOGLE_DRIVE_FOLDER_ID} "${BACKUP_FILE}"
    # if [ $? -eq 0 ]; then
    #     echo "Backup uploaded to Google Drive successfully."
    # else
    #     echo "Failed to upload backup to Google Drive."
    # fi

    # --- Clean up old backups (optional) ---
    # Find and delete backups older than 7 days
    # find "${BACKUP_DIR}" -type f -name "*.sql" -mtime +7 -delete
    # echo "Cleaned up old backups."

else
    echo "Error: Database backup failed."
fi
