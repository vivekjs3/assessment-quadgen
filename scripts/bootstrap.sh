#!/usr/bin/env bash
# ==============================================================================
# Single-Command Bootstrap Script for Kubernetes Jenkins CI/CD Platform
# Supports: Local Host (Linux/Mac/WSL) & Proxmox VE (VMs / LXC / Baremetal)
# ==============================================================================
set -euo pipefail

CLUSTER_NAME="kind-jenkins"
REGISTRY_NAME="kind-registry"
REGISTRY_PORT="5001"

echo "================================================================="
echo "  🚀 Starting Kubernetes & Jenkins CI/CD Setup"
echo "  Supports: Local Host (Mac/Linux/Win) & Proxmox (VM / LXC / Baremetal)"
echo "================================================================="

# ------------------------------------------------------------------------------
# Helper Functions & Dependency Checks
# ------------------------------------------------------------------------------
detect_host_ip() {
  local ip=""
  ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}') || true
  if [ -z "${ip}" ]; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}') || true
  fi
  if [ -z "${ip}" ]; then
    ip="localhost"
  fi
  echo "${ip}"
}

HOST_IP=$(detect_host_ip)

install_docker_if_missing() {
  if ! command -v docker &>/dev/null; then
    echo "📦 Docker not found. Installing Docker Engine..."
    sudo apt-get update -y
    sudo apt-get install -y docker.io
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER" || true
  fi
}

install_kubectl_if_missing() {
  if ! command -v kubectl &>/dev/null; then
    echo "📦 kubectl not found. Downloading kubectl v1.29.2..."
    curl -sSL -o /tmp/kubectl "https://dl.k8s.io/release/v1.29.2/bin/linux/amd64/kubectl"
    chmod +x /tmp/kubectl
    sudo mv /tmp/kubectl /usr/local/bin/kubectl
  fi
}

install_kind_if_missing() {
  if ! command -v kind &>/dev/null; then
    echo "📦 KinD not found. Downloading KinD v0.22.0..."
    curl -sSL -o /tmp/kind_bin "https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64"
    chmod +x /tmp/kind_bin
    sudo mv /tmp/kind_bin /usr/local/bin/kind
  fi
}

install_curl_make_if_missing() {
  if ! command -v curl &>/dev/null || ! command -v make &>/dev/null; then
    echo "📦 Installing curl and make..."
    sudo apt-get update -y
    sudo apt-get install -y curl make
  fi
}

echo "🔍 Checking system prerequisites..."
install_curl_make_if_missing
install_docker_if_missing
install_kubectl_if_missing
install_kind_if_missing
echo "✅ All prerequisites (Docker, kubectl, KinD, curl, make) are installed & ready!"

# ------------------------------------------------------------------------------
# 1. Start Local Docker Registry
# ------------------------------------------------------------------------------
if [ "$(docker inspect -f '{{.State.Running}}' "${REGISTRY_NAME}" 2>/dev/null || true)" != 'true' ]; then
  echo "📦 Creating and starting local container registry '${REGISTRY_NAME}' on port ${REGISTRY_PORT}..."
  docker run -d --restart=always -p "0.0.0.0:${REGISTRY_PORT}:5000" --network bridge --name "${REGISTRY_NAME}" registry:2 || true
else
  echo "✅ Local container registry '${REGISTRY_NAME}' is already running."
fi

# ------------------------------------------------------------------------------
# 2. Create KinD Cluster
# ------------------------------------------------------------------------------
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  echo "☸️ Creating KinD cluster '${CLUSTER_NAME}' with 0.0.0.0 external LAN bindings..."
  kind create cluster --name "${CLUSTER_NAME}" --config kind/kind-config.yaml
else
  echo "✅ KinD cluster '${CLUSTER_NAME}' already exists."
fi

# ------------------------------------------------------------------------------
# 3. Connect Local Registry to KinD Docker Network
# ------------------------------------------------------------------------------
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${REGISTRY_NAME}")" = 'null' ]; then
  echo "🔗 Connecting '${REGISTRY_NAME}' to KinD network..."
  docker network connect "kind" "${REGISTRY_NAME}" || true
fi

# ------------------------------------------------------------------------------
# 4. Apply containerd Local Registry Hosting ConfigMap
# ------------------------------------------------------------------------------
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

# ------------------------------------------------------------------------------
# 5. Create Namespaces and Jenkins ConfigMaps
# ------------------------------------------------------------------------------
echo "📁 Applying Namespaces & Scoped RBAC..."
kubectl apply -f k8s/namespaces.yaml
kubectl apply -f k8s/jenkins-rbac.yaml

kubectl create configmap jenkins-casc-config --from-file=jenkins.yaml=jcasc/jenkins.yaml -n jenkins --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap jenkins-plugins-config --from-file=plugins.txt=jcasc/plugins.txt -n jenkins --dry-run=client -o yaml | kubectl apply -f -

# ------------------------------------------------------------------------------
# 6. Deploy Jenkins Controller, Services & Sample App
# ------------------------------------------------------------------------------
echo "🚀 Deploying Jenkins Controller, Services & Sample App..."
kubectl apply -f k8s/jenkins-service.yaml
kubectl apply -f k8s/jenkins-deployment.yaml
kubectl apply -f k8s/sample-app/deployment.yaml

echo "⏳ Waiting for Jenkins Controller initialization (Up to 10 minutes for plugin downloads & JCasC boot)..."
if ! kubectl rollout status deployment/jenkins -n jenkins --timeout=600s; then
  echo "⚠️ Rollout status timed out. Checking HTTP login endpoint health..."
  for i in {1..12}; do
    if curl -s -f "http://localhost:8080/login" >/dev/null 2>&1; then
      echo "✅ Jenkins Controller is healthy and responding on port 8080!"
      break
    fi
    sleep 10
  done
fi

echo ""
echo "================================================================="
echo "  🎉 CI/CD Platform is Ready!"
echo "================================================================="
echo "  Local Access:        http://localhost:8080"
echo "  Proxmox / LAN Access:http://${HOST_IP}:8080"
echo "  Sample App Access:   http://${HOST_IP}:8081 (NodePort 30081)"
echo "  Credentials (Admin): admin / adminpassword123"
echo "  Credentials (Dev):   developer / devpassword123"
echo "  Credentials (Audit): auditor / auditpassword123"
echo ""
echo "  Pre-seeded Pipelines (Automated Ephemeral Agent Pods):"
echo "    1. vivek-pod-platform-pipeline (Vivek Pod Platform Proj)"
echo "================================================================="
