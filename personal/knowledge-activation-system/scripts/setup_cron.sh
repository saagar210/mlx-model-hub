#!/bin/bash
# Setup cron jobs for Knowledge Activation System automation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Knowledge Activation System - Cron Setup"
echo "========================================="
echo ""
echo "This will set up the following automated tasks:"
echo ""
echo "1. Daily Backup (2:00 AM)"
echo "   - PostgreSQL database dump"
echo "   - Obsidian Knowledge folder archive"
echo "   - Configuration files"
echo "   - 30-day retention"
echo ""
echo "2. Daily Content Generation (3:00 AM)"
echo "   - Generate 5 new technical guides using Ollama"
echo "   - Auto-ingest into database"
echo ""
echo "Add these lines to your crontab (crontab -e):"
echo ""
echo "# Knowledge Activation System - Daily Backup"
echo "0 2 * * * ${SCRIPT_DIR}/daily_backup.sh >> ${PROJECT_DIR}/logs/backup.log 2>&1"
echo ""
echo "# Knowledge Activation System - Daily Content Generation"
echo "0 3 * * * ${SCRIPT_DIR}/daily_content_generation.sh >> ${PROJECT_DIR}/logs/content_generation.log 2>&1"
echo ""
echo "========================================="
echo ""

read -p "Would you like to add these cron jobs automatically? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create temporary crontab file
    TEMP_CRON=$(mktemp)

    # Get existing crontab
    crontab -l > "$TEMP_CRON" 2>/dev/null || true

    # Check if jobs already exist
    if grep -q "Knowledge Activation System" "$TEMP_CRON"; then
        echo "KAS cron jobs already exist. Skipping to avoid duplicates."
        rm "$TEMP_CRON"
        exit 0
    fi

    # Add new jobs
    cat >> "$TEMP_CRON" << EOF

# Knowledge Activation System - Daily Backup
0 2 * * * ${SCRIPT_DIR}/daily_backup.sh >> ${PROJECT_DIR}/logs/backup.log 2>&1

# Knowledge Activation System - Daily Content Generation
0 3 * * * ${SCRIPT_DIR}/daily_content_generation.sh >> ${PROJECT_DIR}/logs/content_generation.log 2>&1
EOF

    # Install new crontab
    crontab "$TEMP_CRON"
    rm "$TEMP_CRON"

    echo "Cron jobs installed successfully!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep -A1 "Knowledge Activation"
else
    echo ""
    echo "Copy the lines above and add them manually using: crontab -e"
fi

echo ""
echo "Logs will be written to: ${PROJECT_DIR}/logs/"
