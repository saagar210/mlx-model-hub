#!/bin/bash

# Perimeter.ai Startup Script

echo "Starting Perimeter.ai..."

# 1. Activate Python Environment and Start Backend
echo "[1/2] Starting Backend Server (FastAPI)..."
source .venv/bin/activate
# Run uvicorn in background, suppress stdout slightly to keep terminal clean-ish, but show errors
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Give it a moment to spin up
sleep 2

# 2. Check if Backend is up (Basic check)
if ps -p $BACKEND_PID > /dev/null; then
   echo "Backend is running (PID: $BACKEND_PID)."
else
   echo "Error: Backend failed to start."
   exit 1
fi

# 3. Start Frontend (Electron + Vite)
echo "[2/2] Starting Frontend (Electron)..."
echo "Press Ctrl+C to exit both services."
npm run dev

# 4. Cleanup when Electron exits
echo "Shutting down backend..."
kill $BACKEND_PID
