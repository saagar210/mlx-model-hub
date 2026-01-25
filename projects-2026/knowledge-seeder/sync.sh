#!/bin/bash
# Knowledge Seeder Automated Sync Script
# Runs weekly via cron to keep KAS knowledge base fresh
#
# Usage: ./sync.sh [--dry-run]
#
# Setup cron (every Sunday at 4 AM):
#   crontab -e
#   0 4 * * 0 /Users/d/claude-code/projects-2026/knowledge-seeder/sync.sh >> ~/logs/knowledge-sync.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

echo "$LOG_PREFIX Starting Knowledge Seeder sync..."

# Check if KAS is running
if ! curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "$LOG_PREFIX ERROR: KAS API is not available at localhost:8000"
    echo "$LOG_PREFIX Start KAS before running sync:"
    echo "$LOG_PREFIX   cd /Users/d/claude-code/personal/knowledge-activation-system"
    echo "$LOG_PREFIX   uv run uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

# Activate virtual environment
cd "$SCRIPT_DIR"
source .venv/bin/activate

# Get current stats before sync
BEFORE=$(curl -sf http://localhost:8000/api/v1/health | jq -r '.stats.total_content')
echo "$LOG_PREFIX KAS before sync: $BEFORE documents"

# Run sync command
DRY_RUN=""
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo "$LOG_PREFIX Running in dry-run mode..."
fi

echo "$LOG_PREFIX Syncing sources..."
python -m knowledge_seeder.cli -L INFO sync $DRY_RUN sources/*.yaml

# Get stats after sync
AFTER=$(curl -sf http://localhost:8000/api/v1/health | jq -r '.stats.total_content')
echo "$LOG_PREFIX KAS after sync: $AFTER documents"

# Calculate difference
DIFF=$((AFTER - BEFORE))
if [[ $DIFF -gt 0 ]]; then
    echo "$LOG_PREFIX Added $DIFF new documents"
elif [[ $DIFF -eq 0 ]]; then
    echo "$LOG_PREFIX No new documents (sources up to date)"
else
    echo "$LOG_PREFIX Document count decreased by $((DIFF * -1)) (possible cleanup)"
fi

echo "$LOG_PREFIX Sync complete!"
