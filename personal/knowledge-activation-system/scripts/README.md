# KAS Service Management Scripts

Scripts for managing the Knowledge Activation System.

## Quick Start

```bash
# Test health
./health-check.sh

# Manual backup
POSTGRES_PORT=5433 ./backup.sh

# Restore from backup
./restore.sh ~/backups/knowledge/knowledge_YYYYMMDD_HHMMSS.sql.gz
```

## Scripts

| Script | Purpose |
|--------|---------|
| `health-check.sh` | Check KAS, PostgreSQL, and Ollama health |
| `backup.sh` | Create PostgreSQL backup with retention |
| `restore.sh` | Restore database from backup |
| `com.kas.api.plist` | launchd service for KAS API |

## Cron Jobs (Already Configured)

```bash
# View current cron
crontab -l

# Current schedule:
# - Health check: every 5 minutes
# - Database backup: daily at 3 AM
# - Knowledge sync: weekly on Sunday at 4 AM
```

## launchd Service (Optional)

To run KAS as a macOS service:

```bash
# Install service
cp com.kas.api.plist ~/Library/LaunchAgents/

# Load service (starts automatically)
launchctl load ~/Library/LaunchAgents/com.kas.api.plist

# Check status
launchctl list | grep kas

# Stop service
launchctl unload ~/Library/LaunchAgents/com.kas.api.plist
```

## Log Files

All logs in `~/logs/`:

| Log | Purpose |
|-----|---------|
| `kas-health.log` | Health check results |
| `kas-backup.log` | Backup job output |
| `kas-api.log` | API server stdout |
| `kas-api-error.log` | API server stderr |
| `knowledge-sync.log` | Weekly sync output |

## Manual Commands

```bash
# Start KAS manually
cd /Users/d/claude-code/personal/knowledge-activation-system
uv run uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000

# Check API health
curl http://localhost:8000/api/v1/health | jq

# Check PostgreSQL
docker exec knowledge-db pg_isready

# Check Ollama
curl http://localhost:11434/api/tags
```

## Troubleshooting

### KAS API Not Starting

1. Check if port 8000 is in use: `lsof -i :8000`
2. Check logs: `tail -f ~/logs/kas-api-error.log`
3. Verify PostgreSQL: `docker ps | grep knowledge-db`

### PostgreSQL Connection Failed

1. Start container: `docker compose up -d`
2. Check port: `docker port knowledge-db`
3. Verify credentials in `.env`

### Ollama Not Available

1. Start Ollama: `ollama serve`
2. Pull model: `ollama pull nomic-embed-text`
3. Test: `curl http://localhost:11434/api/tags`
