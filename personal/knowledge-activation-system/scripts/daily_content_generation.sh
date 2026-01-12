#!/bin/bash
# Daily Content Generation Script
# Run via cron: 0 3 * * * /path/to/daily_content_generation.sh >> /path/to/logs/content_generation.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_DIR}/logs/content_generation.log"
LOCK_FILE="/tmp/kas_content_generation.lock"

# Ensure logs directory exists
mkdir -p "${PROJECT_DIR}/logs"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Another instance is running, exiting"
    exit 1
fi
trap "rm -f $LOCK_FILE" EXIT
touch "$LOCK_FILE"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting daily content generation"

cd "$PROJECT_DIR"

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: Ollama is not running"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Generate 10 new topics per day (customizable)
TOPICS=(
    "Python AsyncIO Patterns"
    "React Server Components Deep Dive"
    "PostgreSQL Performance Tuning"
    "Docker Multi-Stage Builds"
    "TypeScript Utility Types"
    "Git Advanced Workflows"
    "API Design Best Practices"
    "Testing Strategies Guide"
    "CI/CD Pipeline Patterns"
    "Kubernetes Deployment Patterns"
)

# Randomly select 5 topics
SELECTED_TOPICS=($(shuf -e "${TOPICS[@]}" | head -5))

for topic in "${SELECTED_TOPICS[@]}"; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Generating content for: $topic"

    # Generate content using Ollama
    CONTENT=$(curl -s http://localhost:11434/api/generate \
        -d "{
            \"model\": \"qwen2.5:7b\",
            \"prompt\": \"Write a comprehensive technical guide about $topic. Include: overview, key concepts, practical examples with code, best practices, common pitfalls, and resources. Format in Markdown. Make it 10-20KB of useful content.\",
            \"stream\": false
        }" | jq -r '.response' 2>/dev/null)

    if [ -n "$CONTENT" ] && [ "$CONTENT" != "null" ]; then
        # Create filename from topic
        FILENAME=$(echo "$topic" | tr ' ' '-' | tr '[:upper:]' '[:lower:]')
        FILEPATH="/Users/d/Obsidian/Knowledge/Notes/${FILENAME}.md"

        # Write to file with frontmatter
        cat > "$FILEPATH" << EOF
---
type: guide
tags: [generated, daily-batch]
generated_at: $(date '+%Y-%m-%d')
---

# $topic

$CONTENT
EOF

        echo "$(date '+%Y-%m-%d %H:%M:%S') - Created: $FILEPATH"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - WARN: Failed to generate content for: $topic"
    fi

    # Small delay between generations
    sleep 2
done

# Ingest new content into database
echo "$(date '+%Y-%m-%d %H:%M:%S') - Ingesting new content into database"
python cli.py ingest directory /Users/d/Obsidian/Knowledge/Notes 2>&1 | tail -5

# Get updated stats
echo "$(date '+%Y-%m-%d %H:%M:%S') - Current database stats:"
python cli.py stats

echo "$(date '+%Y-%m-%d %H:%M:%S') - Daily content generation complete"
