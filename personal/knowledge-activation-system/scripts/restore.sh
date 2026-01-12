#!/bin/bash
# Knowledge Activation System - Database Restore Script
#
# This script restores a PostgreSQL database from a backup file.
#
# Usage: ./restore.sh <backup_file.sql.gz>
#
# Configuration via environment variables:
#   POSTGRES_HOST: Database host (default: localhost)
#   POSTGRES_PORT: Database port (default: 5432)
#   POSTGRES_USER: Database user (default: knowledge)
#   POSTGRES_DB: Database name (default: knowledge)

set -euo pipefail

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-knowledge}"
POSTGRES_DB="${POSTGRES_DB:-knowledge}"

# Check for backup file argument
if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Example: $0 ~/backups/knowledge/knowledge_20240115_030000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Verify backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "=== Knowledge Activation System - Database Restore ==="
echo ""
echo "WARNING: This will DROP and recreate the database!"
echo "Backup file: ${BACKUP_FILE}"
echo "Target database: ${POSTGRES_DB} on ${POSTGRES_HOST}:${POSTGRES_PORT}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "Starting restore at $(date)"

# Drop and recreate the database
echo "Dropping existing database..."
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"

echo "Creating fresh database..."
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"

# Restore the backup
echo "Restoring from backup..."
gunzip -c "${BACKUP_FILE}" | psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo ""
echo "Restore completed at $(date)"
echo ""
echo "Note: You may need to restart the application to reconnect to the database."
