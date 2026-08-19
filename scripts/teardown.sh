#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="kind-jenkins"
REGISTRY_NAME="kind-registry"

echo "🧹 Tearing down Kubernetes & Jenkins resources..."

kind delete cluster --name "${CLUSTER_NAME}" || true
docker stop "${REGISTRY_NAME}" || true
docker rm "${REGISTRY_NAME}" || true

echo "✅ Teardown complete."
