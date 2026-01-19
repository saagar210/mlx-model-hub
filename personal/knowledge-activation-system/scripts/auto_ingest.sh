#!/bin/bash
# Automated ingestion script for KAS
# Runs hourly via LaunchAgent to ingest new files from Obsidian vault

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VAULT_DIR="${HOME}/Obsidian/Knowledge/Notes"
LOG_DIR="${HOME}/logs"
LOG_FILE="${LOG_DIR}/kas-auto-ingest.log"

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Timestamp function
timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

log() {
    echo "[$(timestamp)] $1" >> "$LOG_FILE"
}

log "Starting auto-ingestion run"

# Check if API is running
if ! curl -s "http://localhost:8000/health" > /dev/null 2>&1; then
    log "ERROR: KAS API is not running"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

# Run ingestion for new/modified files
log "Ingesting from: $VAULT_DIR"

# Use uv run to ensure correct environment
PYTHONPATH=src uv run python cli.py ingest directory "$VAULT_DIR" --skip-existing >> "$LOG_FILE" 2>&1

RESULT=$?

if [ $RESULT -eq 0 ]; then
    log "Auto-ingestion completed successfully"
else
    log "ERROR: Auto-ingestion failed with code $RESULT"
fi

# Log current stats
STATS=$(curl -s "http://localhost:8000/api/v1/content/stats" 2>/dev/null || echo "{}")
DOC_COUNT=$(echo "$STATS" | grep -o '"total_content":[0-9]*' | cut -d: -f2 || echo "unknown")
CHUNK_COUNT=$(echo "$STATS" | grep -o '"total_chunks":[0-9]*' | cut -d: -f2 || echo "unknown")

log "Current stats: $DOC_COUNT documents, $CHUNK_COUNT chunks"

exit $RESULT
