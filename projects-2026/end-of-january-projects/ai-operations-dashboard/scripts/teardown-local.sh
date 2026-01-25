#!/bin/bash
# Tear down local k3d cluster

set -e

echo "=== Tearing Down Langfuse k3d Cluster ==="

# Delete Helm release first
if helm list -n langfuse | grep -q langfuse; then
    echo "Uninstalling Helm release..."
    helm uninstall langfuse -n langfuse || true
fi

# Delete k3d cluster
if k3d cluster list | grep -q "langfuse-dev"; then
    echo "Deleting k3d cluster..."
    k3d cluster delete langfuse-dev
fi

echo ""
echo "=== Teardown Complete ==="
