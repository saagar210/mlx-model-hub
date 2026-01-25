#!/bin/bash
# Deploy Langfuse stack to local k3d cluster

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Deploying Langfuse to k3d ==="

# Check k3d cluster exists
if ! k3d cluster list | grep -q "langfuse-dev"; then
    echo "Creating k3d cluster..."
    k3d cluster create langfuse-dev \
        --port "3002:3000@loadbalancer" \
        --port "5435:5432@loadbalancer" \
        --port "8123:8123@loadbalancer" \
        --port "4566:4566@loadbalancer" \
        --port "9093:9093@loadbalancer" \
        --agents 2 \
        --servers 1 \
        --wait
fi

# Switch context
kubectl config use-context k3d-langfuse-dev

# Create namespace
kubectl create namespace langfuse --dry-run=client -o yaml | kubectl apply -f -

# Deploy with Helm
echo "Installing Langfuse Helm chart..."
helm upgrade --install langfuse "$PROJECT_DIR/helm/langfuse" \
    -f "$PROJECT_DIR/helm/langfuse/values.local.yaml" \
    --namespace langfuse \
    --wait \
    --timeout 10m

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=langfuse -n langfuse --timeout=300s || true

echo ""
kubectl get pods -n langfuse
echo ""
echo "Access Langfuse at: http://localhost:3002"
echo ""
