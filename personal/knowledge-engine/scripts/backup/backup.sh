#!/bin/bash
# Knowledge Engine Backup Script
# Backs up PostgreSQL, Qdrant, and configuration files
#
# Usage:
#   ./backup.sh                    # Full backup with default settings
#   ./backup.sh --postgres-only    # Backup PostgreSQL only
#   ./backup.sh --qdrant-only      # Backup Qdrant only
#   ./backup.sh --config-only      # Backup config files only
#   ./backup.sh --retention 7      # Keep backups for 7 days
#
# Environment variables:
#   BACKUP_DIR          - Backup storage directory (default: ./backups)
#   POSTGRES_HOST       - PostgreSQL host (default: localhost)
#   POSTGRES_PORT       - PostgreSQL port (default: 5432)
#   POSTGRES_USER       - PostgreSQL user (default: knowledge_engine)
#   POSTGRES_PASSWORD   - PostgreSQL password (required)
#   POSTGRES_DB         - PostgreSQL database (default: knowledge_engine)
#   QDRANT_URL          - Qdrant URL (default: http://localhost:6333)
#   RETENTION_DAYS      - Days to keep backups (default: 30)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"; }

# Configuration with defaults
BACKUP_DIR="${BACKUP_DIR:-./backups}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-knowledge_engine}"
POSTGRES_DB="${POSTGRES_DB:-knowledge_engine}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Timestamp for this backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_SUBDIR="${BACKUP_DIR}/${TIMESTAMP}"

# Flags
BACKUP_POSTGRES=true
BACKUP_QDRANT=true
BACKUP_CONFIG=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --postgres-only)
            BACKUP_QDRANT=false
            BACKUP_CONFIG=false
            shift
            ;;
        --qdrant-only)
            BACKUP_POSTGRES=false
            BACKUP_CONFIG=false
            shift
            ;;
        --config-only)
            BACKUP_POSTGRES=false
            BACKUP_QDRANT=false
            shift
            ;;
        --retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        -h|--help)
            echo "Knowledge Engine Backup Script"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --postgres-only    Backup PostgreSQL only"
            echo "  --qdrant-only      Backup Qdrant only"
            echo "  --config-only      Backup config files only"
            echo "  --retention N      Keep backups for N days (default: 30)"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create backup directory structure
mkdir -p "${BACKUP_SUBDIR}"
log_info "Created backup directory: ${BACKUP_SUBDIR}"

# Track backup status
BACKUP_STATUS=0

# Function to backup PostgreSQL
backup_postgres() {
    log_info "Starting PostgreSQL backup..."

    if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
        log_error "POSTGRES_PASSWORD environment variable is required"
        return 1
    fi

    local pg_backup_file="${BACKUP_SUBDIR}/postgres_${POSTGRES_DB}.sql.gz"

    PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        --format=custom \
        --compress=9 \
        --verbose \
        2>&1 | gzip > "${pg_backup_file}"

    local backup_size=$(du -sh "${pg_backup_file}" | cut -f1)
    log_success "PostgreSQL backup complete: ${pg_backup_file} (${backup_size})"

    # Verify backup
    if [[ -f "${pg_backup_file}" ]] && [[ -s "${pg_backup_file}" ]]; then
        log_info "PostgreSQL backup verification passed"
    else
        log_error "PostgreSQL backup verification failed - file is empty or missing"
        return 1
    fi
}

# Function to backup Qdrant collections
backup_qdrant() {
    log_info "Starting Qdrant backup..."

    local qdrant_backup_dir="${BACKUP_SUBDIR}/qdrant"
    mkdir -p "${qdrant_backup_dir}"

    # Get list of collections
    local collections
    collections=$(curl -s "${QDRANT_URL}/collections" | jq -r '.result.collections[].name' 2>/dev/null) || {
        log_error "Failed to get Qdrant collections. Is Qdrant running?"
        return 1
    }

    if [[ -z "${collections}" ]]; then
        log_warn "No Qdrant collections found to backup"
        return 0
    fi

    # Create snapshots for each collection
    for collection in ${collections}; do
        log_info "Creating snapshot for collection: ${collection}"

        # Create snapshot via API
        local response
        response=$(curl -s -X POST "${QDRANT_URL}/collections/${collection}/snapshots")

        local snapshot_name
        snapshot_name=$(echo "${response}" | jq -r '.result.name' 2>/dev/null)

        if [[ -z "${snapshot_name}" ]] || [[ "${snapshot_name}" == "null" ]]; then
            log_error "Failed to create snapshot for ${collection}: ${response}"
            continue
        fi

        # Download snapshot
        local snapshot_file="${qdrant_backup_dir}/${collection}_${snapshot_name}"
        curl -s -o "${snapshot_file}" "${QDRANT_URL}/collections/${collection}/snapshots/${snapshot_name}"

        local backup_size=$(du -sh "${snapshot_file}" | cut -f1)
        log_success "Collection ${collection} backed up: ${snapshot_file} (${backup_size})"
    done

    log_success "Qdrant backup complete"
}

# Function to backup configuration files
backup_config() {
    log_info "Starting configuration backup..."

    local config_backup_dir="${BACKUP_SUBDIR}/config"
    mkdir -p "${config_backup_dir}"

    # Backup .env file if exists (remove sensitive values)
    if [[ -f ".env" ]]; then
        # Mask sensitive values in backup
        sed -E 's/(PASSWORD|SECRET|KEY|TOKEN)=.*/\1=***MASKED***/gi' .env > "${config_backup_dir}/.env.masked"
        log_info "Backed up .env (with masked secrets)"
    fi

    # Backup docker-compose files
    for compose_file in docker-compose*.yml docker-compose*.yaml; do
        if [[ -f "${compose_file}" ]]; then
            cp "${compose_file}" "${config_backup_dir}/"
            log_info "Backed up ${compose_file}"
        fi
    done

    # Backup monitoring configuration
    if [[ -d "monitoring" ]]; then
        cp -r monitoring "${config_backup_dir}/"
        log_info "Backed up monitoring configuration"
    fi

    log_success "Configuration backup complete"
}

# Function to cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up backups older than ${RETENTION_DAYS} days..."

    local deleted_count=0

    # Find and delete old backup directories
    while IFS= read -r old_backup; do
        if [[ -d "${old_backup}" ]]; then
            rm -rf "${old_backup}"
            log_info "Deleted old backup: ${old_backup}"
            ((deleted_count++))
        fi
    done < <(find "${BACKUP_DIR}" -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -name "20*" 2>/dev/null)

    log_success "Cleanup complete. Deleted ${deleted_count} old backup(s)"
}

# Function to create backup manifest
create_manifest() {
    local manifest_file="${BACKUP_SUBDIR}/manifest.json"

    cat > "${manifest_file}" << EOF
{
    "backup_timestamp": "${TIMESTAMP}",
    "backup_date": "$(date -Iseconds)",
    "components": {
        "postgres": ${BACKUP_POSTGRES},
        "qdrant": ${BACKUP_QDRANT},
        "config": ${BACKUP_CONFIG}
    },
    "settings": {
        "postgres_host": "${POSTGRES_HOST}",
        "postgres_db": "${POSTGRES_DB}",
        "qdrant_url": "${QDRANT_URL}",
        "retention_days": ${RETENTION_DAYS}
    },
    "files": $(find "${BACKUP_SUBDIR}" -type f -printf '"%p"\n' | jq -s '.')
}
EOF

    log_info "Created backup manifest: ${manifest_file}"
}

# Main execution
main() {
    log_info "=========================================="
    log_info "Knowledge Engine Backup Starting"
    log_info "Timestamp: ${TIMESTAMP}"
    log_info "Backup Directory: ${BACKUP_SUBDIR}"
    log_info "=========================================="

    # Run selected backups
    if [[ "${BACKUP_POSTGRES}" == "true" ]]; then
        backup_postgres || BACKUP_STATUS=1
    fi

    if [[ "${BACKUP_QDRANT}" == "true" ]]; then
        backup_qdrant || BACKUP_STATUS=1
    fi

    if [[ "${BACKUP_CONFIG}" == "true" ]]; then
        backup_config || BACKUP_STATUS=1
    fi

    # Create manifest
    create_manifest

    # Cleanup old backups
    cleanup_old_backups

    # Calculate total backup size
    local total_size=$(du -sh "${BACKUP_SUBDIR}" | cut -f1)

    log_info "=========================================="
    if [[ ${BACKUP_STATUS} -eq 0 ]]; then
        log_success "Backup completed successfully!"
    else
        log_warn "Backup completed with some errors"
    fi
    log_info "Total backup size: ${total_size}"
    log_info "Location: ${BACKUP_SUBDIR}"
    log_info "=========================================="

    exit ${BACKUP_STATUS}
}

main
