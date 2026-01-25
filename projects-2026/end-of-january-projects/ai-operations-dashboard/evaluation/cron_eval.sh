#!/bin/bash
# Cron wrapper for continuous evaluation
# Add to crontab: */15 * * * * /Users/d/claude-code/projects-2026/end-of-january-projects/ai-operations-dashboard/evaluation/cron_eval.sh

set -e

# Project directory
PROJECT_DIR="/Users/d/claude-code/projects-2026/end-of-january-projects/ai-operations-dashboard"
LOG_DIR="/Users/d/logs"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Default environment variables
export LANGFUSE_HOST="${LANGFUSE_HOST:-http://localhost:3002}"
export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

# Activate virtual environment if it exists
if [ -d "$PROJECT_DIR/.venv" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

# Run evaluation
cd "$PROJECT_DIR"
python evaluation/continuous_eval.py >> "$LOG_DIR/langfuse-eval.log" 2>&1

# Rotate logs if too large (> 10MB)
if [ -f "$LOG_DIR/langfuse-eval.log" ]; then
    size=$(stat -f%z "$LOG_DIR/langfuse-eval.log" 2>/dev/null || stat -c%s "$LOG_DIR/langfuse-eval.log" 2>/dev/null)
    if [ "$size" -gt 10485760 ]; then
        mv "$LOG_DIR/langfuse-eval.log" "$LOG_DIR/langfuse-eval.log.old"
    fi
fi
