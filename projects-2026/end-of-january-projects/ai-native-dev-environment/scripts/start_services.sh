#!/bin/bash
# Start all services for the AI-Native Development Environment
set -e

echo "Starting AI-Native Development Environment services..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Warning: Docker is not running. PostgreSQL may not start."
fi

# Start PostgreSQL (via Docker Compose in KAS)
echo "Starting PostgreSQL..."
KAS_DIR=~/claude-code/personal/knowledge-activation-system
if [ -f "$KAS_DIR/docker/docker-compose.yml" ]; then
    docker compose -f "$KAS_DIR/docker/docker-compose.yml" up -d postgres 2>/dev/null || true
fi

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
sleep 3

# Start Redis (if not running)
echo "Starting Redis..."
if ! pgrep -x "redis-server" > /dev/null; then
    redis-server --daemonize yes 2>/dev/null || echo "Redis may already be running"
fi

# Check Ollama
echo "Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "Warning: Ollama is not running. Please start it manually."
fi

# Security: Default to localhost binding. Set UCE_BIND_HOST=0.0.0.0 to expose externally.
# WARNING: Exposing services externally without authentication is a security risk!
BIND_HOST="${UCE_BIND_HOST:-127.0.0.1}"
if [ "$BIND_HOST" = "0.0.0.0" ]; then
    echo "WARNING: Services will be exposed to the network. Ensure proper firewall rules!"
fi

# Start KAS API
echo "Starting KAS API on port 8000 (host: $BIND_HOST)..."
if [ -d "$KAS_DIR" ]; then
    cd "$KAS_DIR"
    nohup uv run uvicorn knowledge.api.main:app --host "$BIND_HOST" --port 8000 > /tmp/kas.log 2>&1 &
    echo "KAS PID: $!"
fi

# Start LocalCrew API
echo "Starting LocalCrew API on port 8001 (host: $BIND_HOST)..."
LOCALCREW_DIR=~/claude-code/personal/crewai-automation-platform
if [ -d "$LOCALCREW_DIR" ]; then
    cd "$LOCALCREW_DIR"
    nohup uv run uvicorn localcrew.api.main:app --host "$BIND_HOST" --port 8001 > /tmp/localcrew.log 2>&1 &
    echo "LocalCrew PID: $!"
fi

# Start UCE Dashboard
echo "Starting UCE Dashboard on port 8002 (host: $BIND_HOST)..."
UCE_DIR=~/claude-code/projects-2026/end-of-january-projects/ai-native-dev-environment
if [ -d "$UCE_DIR" ]; then
    cd "$UCE_DIR"
    nohup uv run uvicorn universal_context_engine.dashboard.api:app --host "$BIND_HOST" --port 8002 > /tmp/uce-dashboard.log 2>&1 &
    echo "UCE Dashboard PID: $!"
fi

echo ""
echo "Services starting..."
echo "  - KAS API: http://localhost:8000"
echo "  - LocalCrew API: http://localhost:8001"
echo "  - UCE Dashboard: http://localhost:8002"
echo ""
echo "Check logs in /tmp/*.log"
echo "Use 'scripts/stop_services.sh' to stop all services"
