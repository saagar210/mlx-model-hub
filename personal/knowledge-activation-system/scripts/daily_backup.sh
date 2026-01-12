#!/bin/bash
# Daily Backup Script for Knowledge Activation System
# Run via cron: 0 2 * * * /path/to/daily_backup.sh >> /path/to/logs/backup.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
LOG_FILE="${PROJECT_DIR}/logs/backup.log"
RETENTION_DAYS=30

# Ensure directories exist
mkdir -p "$BACKUP_DIR"
mkdir -p "${PROJECT_DIR}/logs"

DATE=$(date '+%Y-%m-%d')
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting daily backup"

cd "$PROJECT_DIR"

# Database backup
echo "$(date '+%Y-%m-%d %H:%M:%S') - Backing up PostgreSQL database"
docker exec knowledge-db pg_dump -U knowledge knowledge > "${BACKUP_DIR}/db_${TIMESTAMP}.sql"
gzip "${BACKUP_DIR}/db_${TIMESTAMP}.sql"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Database backup: ${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"

# Obsidian vault backup (just the Knowledge folder)
echo "$(date '+%Y-%m-%d %H:%M:%S') - Backing up Obsidian Knowledge folder"
tar -czf "${BACKUP_DIR}/obsidian_${TIMESTAMP}.tar.gz" -C /Users/d/Obsidian Knowledge
echo "$(date '+%Y-%m-%d %H:%M:%S') - Obsidian backup: ${BACKUP_DIR}/obsidian_${TIMESTAMP}.tar.gz"

# Configuration backup
echo "$(date '+%Y-%m-%d %H:%M:%S') - Backing up configuration files"
tar -czf "${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz" \
    .env \
    docker-compose.yml \
    pyproject.toml \
    2>/dev/null || true
echo "$(date '+%Y-%m-%d %H:%M:%S') - Config backup: ${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz"

# Cleanup old backups
echo "$(date '+%Y-%m-%d %H:%M:%S') - Cleaning up backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

# Show backup summary
echo "$(date '+%Y-%m-%d %H:%M:%S') - Backup summary:"
du -sh "${BACKUP_DIR}"/*.gz 2>/dev/null | tail -5

# Verify latest backup
LATEST_DB="${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"
if [ -f "$LATEST_DB" ] && [ -s "$LATEST_DB" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Backup verification: SUCCESS ($(du -h "$LATEST_DB" | cut -f1))"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: Backup verification FAILED"
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Daily backup complete"
