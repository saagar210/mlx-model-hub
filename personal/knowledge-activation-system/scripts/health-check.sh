#!/bin/bash
# KAS Health Check Script
# Checks KAS API health and alerts on failures
#
# Usage: ./health-check.sh
#
# Setup cron (every 5 minutes):
#   */5 * * * * /Users/d/claude-code/personal/knowledge-activation-system/scripts/health-check.sh

set -e

LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"
LOG_FILE="$HOME/logs/kas-health.log"
KAS_URL="${KAS_API_URL:-http://localhost:8000}"

# Function to send macOS notification
notify() {
    local title="$1"
    local message="$2"
    osascript -e "display notification \"$message\" with title \"$title\"" 2>/dev/null || true
}

# Function to log
log() {
    echo "$LOG_PREFIX $1" >> "$LOG_FILE"
}

# Check KAS API
check_kas() {
    local response
    local status

    response=$(curl -sf "$KAS_URL/api/v1/health" 2>&1) || {
        log "ERROR: KAS API not responding at $KAS_URL"
        notify "KAS Alert" "API not responding!"
        return 1
    }

    status=$(echo "$response" | jq -r '.status' 2>/dev/null)
    if [[ "$status" != "healthy" ]]; then
        log "WARNING: KAS status is '$status'"
        notify "KAS Alert" "Status: $status"
        return 1
    fi

    local docs=$(echo "$response" | jq -r '.stats.total_content' 2>/dev/null)
    local chunks=$(echo "$response" | jq -r '.stats.total_chunks' 2>/dev/null)
    log "OK: KAS healthy - $docs docs, $chunks chunks"
    return 0
}

# Check PostgreSQL
check_postgres() {
    if ! docker ps --format '{{.Names}}' | grep -q 'knowledge-db'; then
        log "ERROR: PostgreSQL container not running"
        notify "KAS Alert" "PostgreSQL container down!"
        return 1
    fi

    if ! docker exec knowledge-db pg_isready -q 2>/dev/null; then
        log "ERROR: PostgreSQL not ready"
        notify "KAS Alert" "PostgreSQL not ready!"
        return 1
    fi

    log "OK: PostgreSQL healthy"
    return 0
}

# Check Ollama
check_ollama() {
    if ! curl -sf "http://localhost:11434/api/tags" > /dev/null 2>&1; then
        log "WARNING: Ollama not responding (embeddings may fail)"
        return 1
    fi

    log "OK: Ollama healthy"
    return 0
}

# Main checks
main() {
    local exit_code=0

    mkdir -p "$(dirname "$LOG_FILE")"

    check_postgres || exit_code=1
    check_ollama || exit_code=1
    check_kas || exit_code=1

    if [[ $exit_code -eq 0 ]]; then
        log "All checks passed"
    else
        log "Some checks failed (exit code: $exit_code)"
    fi

    exit $exit_code
}

main
