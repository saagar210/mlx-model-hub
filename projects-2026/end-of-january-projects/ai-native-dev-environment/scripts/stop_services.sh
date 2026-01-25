#!/bin/bash
# Stop all AI-Native Development Environment services

echo "Stopping AI-Native Development Environment services..."

# Stop UCE Dashboard
pkill -f "uvicorn universal_context_engine.dashboard" 2>/dev/null || true

# Stop LocalCrew
pkill -f "uvicorn localcrew.api" 2>/dev/null || true

# Stop KAS
pkill -f "uvicorn knowledge.api" 2>/dev/null || true

echo "Services stopped."
echo "Note: PostgreSQL and Redis are left running for other applications."
