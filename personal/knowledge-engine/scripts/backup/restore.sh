#!/bin/bash
# Knowledge Engine Restore Script
# Restores PostgreSQL and Qdrant from backup
#
# Usage:
#   ./restore.sh <backup_directory>              # Full restore
#   ./restore.sh <backup_directory> --postgres-only
#   ./restore.sh <backup_directory> --qdrant-only
#   ./restore.sh <backup_directory> --dry-run    # Preview without changes
#
# Environment variables:
#   POSTGRES_HOST       - PostgreSQL host (default: localhost)
#   POSTGRES_PORT       - PostgreSQL port (default: 5432)
#   POSTGRES_USER       - PostgreSQL user (default: knowledge_engine)
#   POSTGRES_PASSWORD   - PostgreSQL password (required)
#   POSTGRES_DB         - PostgreSQL database (default: knowledge_engine)
#   QDRANT_URL          - Qdrant URL (default: http://localhost:6333)

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
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-knowledge_engine}"
POSTGRES_DB="${POSTGRES_DB:-knowledge_engine}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"

# Flags
RESTORE_POSTGRES=true
RESTORE_QDRANT=true
DRY_RUN=false

# Parse arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <backup_directory> [options]"
    echo ""
    echo "Options:"
    echo "  --postgres-only    Restore PostgreSQL only"
    echo "  --qdrant-only      Restore Qdrant only"
    echo "  --dry-run          Preview restore without making changes"
    echo "  -h, --help         Show this help message"
    exit 1
fi

BACKUP_DIR="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --postgres-only)
            RESTORE_QDRANT=false
            shift
            ;;
        --qdrant-only)
            RESTORE_POSTGRES=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Knowledge Engine Restore Script"
            echo ""
            echo "Usage: $0 <backup_directory> [options]"
            echo ""
            echo "Options:"
            echo "  --postgres-only    Restore PostgreSQL only"
            echo "  --qdrant-only      Restore Qdrant only"
            echo "  --dry-run          Preview restore without making changes"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate backup directory
if [[ ! -d "${BACKUP_DIR}" ]]; then
    log_error "Backup directory not found: ${BACKUP_DIR}"
    exit 1
fi

# Check for manifest
MANIFEST_FILE="${BACKUP_DIR}/manifest.json"
if [[ -f "${MANIFEST_FILE}" ]]; then
    log_info "Found backup manifest: ${MANIFEST_FILE}"
    log_info "Backup date: $(jq -r '.backup_date' "${MANIFEST_FILE}")"
fi

# Function to restore PostgreSQL
restore_postgres() {
    log_info "Starting PostgreSQL restore..."

    if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
        log_error "POSTGRES_PASSWORD environment variable is required"
        return 1
    fi

    # Find PostgreSQL backup file
    local pg_backup_file
    pg_backup_file=$(find "${BACKUP_DIR}" -name "postgres_*.sql.gz" -o -name "postgres_*.dump" | head -1)

    if [[ -z "${pg_backup_file}" ]]; then
        log_error "No PostgreSQL backup file found in ${BACKUP_DIR}"
        return 1
    fi

    log_info "Found PostgreSQL backup: ${pg_backup_file}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY RUN] Would restore PostgreSQL from: ${pg_backup_file}"
        return 0
    fi

    # Warning before destructive operation
    log_warn "This will DROP and recreate the database: ${POSTGRES_DB}"
    log_warn "All existing data will be lost!"
    read -p "Are you sure you want to continue? (yes/no): " confirm

    if [[ "${confirm}" != "yes" ]]; then
        log_info "PostgreSQL restore cancelled"
        return 0
    fi

    # Drop and recreate database
    log_info "Dropping existing database..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d postgres \
        -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"

    log_info "Creating new database..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d postgres \
        -c "CREATE DATABASE ${POSTGRES_DB};"

    # Restore from backup
    log_info "Restoring from backup..."
    if [[ "${pg_backup_file}" == *.gz ]]; then
        gunzip -c "${pg_backup_file}" | PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
            -h "${POSTGRES_HOST}" \
            -p "${POSTGRES_PORT}" \
            -U "${POSTGRES_USER}" \
            -d "${POSTGRES_DB}" \
            --verbose
    else
        PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
            -h "${POSTGRES_HOST}" \
            -p "${POSTGRES_PORT}" \
            -U "${POSTGRES_USER}" \
            -d "${POSTGRES_DB}" \
            --verbose \
            "${pg_backup_file}"
    fi

    log_success "PostgreSQL restore complete"
}

# Function to restore Qdrant collections
restore_qdrant() {
    log_info "Starting Qdrant restore..."

    local qdrant_backup_dir="${BACKUP_DIR}/qdrant"

    if [[ ! -d "${qdrant_backup_dir}" ]]; then
        log_warn "No Qdrant backup directory found: ${qdrant_backup_dir}"
        return 0
    fi

    # Find snapshot files
    local snapshot_files
    snapshot_files=$(find "${qdrant_backup_dir}" -type f 2>/dev/null)

    if [[ -z "${snapshot_files}" ]]; then
        log_warn "No Qdrant snapshots found to restore"
        return 0
    fi

    for snapshot_file in ${snapshot_files}; do
        # Extract collection name from filename
        local filename=$(basename "${snapshot_file}")
        local collection_name=$(echo "${filename}" | sed 's/_[^_]*$//')

        log_info "Restoring collection: ${collection_name}"

        if [[ "${DRY_RUN}" == "true" ]]; then
            log_info "[DRY RUN] Would restore collection ${collection_name} from: ${snapshot_file}"
            continue
        fi

        # Warning before destructive operation
        log_warn "This will overwrite collection: ${collection_name}"
        read -p "Continue with ${collection_name}? (yes/no): " confirm

        if [[ "${confirm}" != "yes" ]]; then
            log_info "Skipping ${collection_name}"
            continue
        fi

        # Upload snapshot and recover
        log_info "Uploading snapshot for ${collection_name}..."

        # First, upload the snapshot file
        curl -s -X POST \
            "${QDRANT_URL}/collections/${collection_name}/snapshots/upload?priority=snapshot" \
            -H "Content-Type: multipart/form-data" \
            -F "snapshot=@${snapshot_file}"

        log_success "Collection ${collection_name} restored"
    done

    log_success "Qdrant restore complete"
}

# Main execution
main() {
    log_info "=========================================="
    log_info "Knowledge Engine Restore Starting"
    log_info "Backup Directory: ${BACKUP_DIR}"
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_warn "DRY RUN MODE - No changes will be made"
    fi
    log_info "=========================================="

    local status=0

    # Run selected restores
    if [[ "${RESTORE_POSTGRES}" == "true" ]]; then
        restore_postgres || status=1
    fi

    if [[ "${RESTORE_QDRANT}" == "true" ]]; then
        restore_qdrant || status=1
    fi

    log_info "=========================================="
    if [[ ${status} -eq 0 ]]; then
        log_success "Restore completed successfully!"
    else
        log_warn "Restore completed with some errors"
    fi
    log_info "=========================================="

    exit ${status}
}

main
