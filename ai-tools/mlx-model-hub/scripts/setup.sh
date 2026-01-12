#!/bin/bash
# MLX Model Hub Setup Script
# Sets up the development environment and infrastructure

set -e

echo "🚀 MLX Model Hub Setup"
echo "======================"

# Check prerequisites
echo ""
echo "📋 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop."
    exit 1
fi
echo "✅ Docker found"

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please update Docker Desktop."
    exit 1
fi
echo "✅ Docker Compose found"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed."
    exit 1
fi
echo "✅ Python 3 found: $(python3 --version)"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed."
    exit 1
fi
echo "✅ Node.js found: $(node --version)"

# Check uv (optional but recommended)
if command -v uv &> /dev/null; then
    echo "✅ uv found: $(uv --version)"
    USE_UV=true
else
    echo "⚠️  uv not found - using pip instead (install uv for faster dependency management)"
    USE_UV=false
fi

# Navigate to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo ""
echo "📁 Project root: $PROJECT_ROOT"

# Create storage directories
echo ""
echo "📂 Creating storage directories..."
mkdir -p storage/active storage/archive
echo "✅ Storage directories created"

# Setup backend
echo ""
echo "🐍 Setting up backend..."
cd "$PROJECT_ROOT/backend"

if [ "$USE_UV" = true ]; then
    echo "   Installing dependencies with uv..."
    uv sync
else
    echo "   Installing dependencies with pip..."
    pip install -e .
fi
echo "✅ Backend dependencies installed"

# Setup frontend
echo ""
echo "⚛️  Setting up frontend..."
cd "$PROJECT_ROOT/frontend"

if command -v pnpm &> /dev/null; then
    echo "   Installing dependencies with pnpm..."
    pnpm install
elif command -v npm &> /dev/null; then
    echo "   Installing dependencies with npm..."
    npm install
else
    echo "❌ Neither pnpm nor npm found. Please install Node.js/npm."
    exit 1
fi
echo "✅ Frontend dependencies installed"

# Setup Docker services
echo ""
echo "🐳 Setting up Docker services..."
cd "$PROJECT_ROOT"

echo "   Starting PostgreSQL, Prometheus, Grafana, and MLflow..."
docker compose up -d postgres prometheus grafana mlflow

# Wait for services to be healthy
echo "   Waiting for services to start..."
sleep 10

# Check service health
echo ""
echo "📊 Checking service status..."

if docker compose ps | grep -q "mlx-hub-postgres.*healthy\|mlx-hub-postgres.*running"; then
    echo "✅ PostgreSQL: Running on port 5434"
else
    echo "⚠️  PostgreSQL: Not ready yet (this is normal on first run)"
fi

if curl -s http://localhost:9090/-/ready > /dev/null 2>&1; then
    echo "✅ Prometheus: Running on http://localhost:9090"
else
    echo "⚠️  Prometheus: Starting..."
fi

if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
    echo "✅ Grafana: Running on http://localhost:3001 (admin/admin)"
else
    echo "⚠️  Grafana: Starting..."
fi

if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "✅ MLflow: Running on http://localhost:5001"
else
    echo "⚠️  MLflow: Starting..."
fi

# Create .env file if it doesn't exist
echo ""
echo "📝 Checking environment configuration..."
if [ ! -f "$PROJECT_ROOT/backend/.env" ]; then
    cat > "$PROJECT_ROOT/backend/.env" << EOF
# MLX Model Hub Backend Configuration
DATABASE_URL=postgresql+asyncpg://mlxhub:mlxhub@localhost:5434/mlxhub
MLFLOW_TRACKING_URI=http://localhost:5001
DEBUG=true
EOF
    echo "✅ Created backend/.env with default settings"
else
    echo "✅ backend/.env already exists"
fi

echo ""
echo "========================================"
echo "🎉 Setup complete!"
echo "========================================"
echo ""
echo "To start the application:"
echo ""
echo "  Backend:"
echo "    cd backend && uv run uvicorn mlx_hub.main:app --reload"
echo ""
echo "  Frontend:"
echo "    cd frontend && pnpm dev"
echo ""
echo "Service URLs:"
echo "  - Frontend:    http://localhost:3000"
echo "  - Backend API: http://localhost:8000"
echo "  - API Docs:    http://localhost:8000/docs"
echo "  - Grafana:     http://localhost:3001 (admin/admin)"
echo "  - Prometheus:  http://localhost:9090"
echo "  - MLflow:      http://localhost:5001"
echo ""
echo "To stop Docker services:"
echo "  docker compose down"
echo ""
