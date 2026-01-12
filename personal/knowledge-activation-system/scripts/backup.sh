#!/bin/bash
# Knowledge Activation System - Database Backup Script
#
# This script creates compressed backups of the PostgreSQL database.
# Recommended to run via cron: 0 3 * * * /path/to/backup.sh
#
# Configuration via environment variables:
#   BACKUP_DIR: Directory to store backups (default: ~/backups/knowledge)
#   BACKUP_RETENTION_DAYS: Days to keep backups (default: 30)
#   POSTGRES_HOST: Database host (default: localhost)
#   POSTGRES_PORT: Database port (default: 5432)
#   POSTGRES_USER: Database user (default: knowledge)
#   POSTGRES_DB: Database name (default: knowledge)

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/knowledge}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-knowledge}"
POSTGRES_DB="${POSTGRES_DB:-knowledge}"

# Timestamp for backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/knowledge_${TIMESTAMP}.sql.gz"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

echo "Starting backup at $(date)"
echo "Backup file: ${BACKUP_FILE}"

# Create the backup using pg_dump
# Uses PGPASSWORD from environment if set, otherwise relies on .pgpass or peer auth
if pg_dump -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${BACKUP_FILE}"; then
    echo "Backup completed successfully"

    # Get backup file size
    BACKUP_SIZE=$(ls -lh "${BACKUP_FILE}" | awk '{print $5}')
    echo "Backup size: ${BACKUP_SIZE}"
else
    echo "ERROR: Backup failed!"
    exit 1
fi

# Clean up old backups
echo "Cleaning up backups older than ${BACKUP_RETENTION_DAYS} days..."
DELETED_COUNT=$(find "${BACKUP_DIR}" -name "knowledge_*.sql.gz" -mtime +${BACKUP_RETENTION_DAYS} -print -delete | wc -l)
echo "Deleted ${DELETED_COUNT} old backup(s)"

# List recent backups
echo ""
echo "Recent backups:"
ls -lht "${BACKUP_DIR}/knowledge_"*.sql.gz 2>/dev/null | head -5 || echo "No backups found"

echo ""
echo "Backup completed at $(date)"
