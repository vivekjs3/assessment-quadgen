# 🚨 RUNBOOK: Jenkins on Kubernetes Ephemeral CI/CD Platform

> **Audience:** On-Call Engineers, SREs, Platform Engineers  
> **Environment:** In-Cluster Jenkins Controller + Ephemeral Kubernetes Agent Pods  
> **Severity:** High / Critical  

---

## Table of Contents
1. [Incident Overview & Quick Triage](#1-incident-overview--quick-triage)
2. [Scenario A: Ephemeral Build Agent Pods Failing to Spawn or Register](#2-scenario-a-ephemeral-build-agent-pods-failing-to-spawn-or-register)
3. [Scenario B: Controller CrashLoopBackOff or Init Container Plugin Failure](#3-scenario-b-controller-crashloopbackoff-or-init-container-plugin-failure)
4. [Scenario C: Pipeline Deployment RBAC Permission Denied (403 Forbidden)](#4-scenario-c-pipeline-deployment-rbac-permission-denied-403-forbidden)
5. [Scenario D: ImagePullBackOff / ErrImagePull from Local In-Cluster Registry](#5-scenario-d-imagepullbackoff--errimagepull-from-local-in-cluster-registry)
6. [Emergency Recovery & Escalation](#6-emergency-recovery--escalation)

---

## 1. Incident Overview & Quick Triage

When paged for a build failure or unresponsive CI/CD environment, run this 30-second triage checklist:

```bash
# 1. Check cluster health and node status
kubectl get nodes

# 2. Check Jenkins controller pod status and restarts
kubectl get pods -n jenkins -o wide

# 3. Check for any pending or crashing ephemeral agent pods
kubectl get pods -n jenkins -l jenkins=slave --show-labels

# 4. Check recently deployed workloads
kubectl get pods -n sample-app
```

---

## 2. Scenario A: Ephemeral Build Agent Pods Failing to Spawn or Register

### 🔴 Symptom
- Jenkins pipeline queue displays: `"Waiting for next available executor on 'k8s-builder'..."` indefinitely.
- Build logs indicate: `JNLP agent connected, but handshake timed out` or pod disappears after ~100 seconds with `Container terminated before registering with Jenkins`.

### 🔍 Cause
1. **JNLP Tunnel Mismatch:** Jenkins agent pod cannot resolve `jenkins-agent.jenkins.svc.cluster.local:50000` or port 50000 is blocked/not bound.
2. **Kubernetes Cloud URL Configuration:** `jenkinsUrl` or `jenkinsTunnel` configured in JCasC has a typo or points to external `localhost` instead of the internal cluster service DNS.
3. **Resource Quotas/Exhaustion:** The cluster has run out of CPU/Memory requests, preventing the ephemeral pod from scheduling.

### 🩺 Step-by-Step Diagnosis

#### Step 1: Check Jenkins System Logs for Kubernetes Cloud Events
```bash
# Search Jenkins controller logs for agent provisioning errors
kubectl logs -n jenkins -l app.kubernetes.io/name=jenkins -c jenkins --tail=200 | grep -iE "kubernetes|provision|agent|jnlp"
```

#### Step 2: Check whether Kubernetes attempted to create the agent pod
```bash
# Watch for agent pod creation during build
kubectl get pods -n jenkins -w
```
If a pod named `sample-app-pipeline-<build-id>` appears and immediately dies or stays in `ContainerCreating` / `Pending`:
```bash
kubectl describe pod <agent-pod-name> -n jenkins
```
Look for events:
- `FailedScheduling`: Node CPU/memory capacity exceeded.
- `FailedMount`: ConfigMap or secret missing.

#### Step 3: Verify JNLP Service and Port
```bash
kubectl get svc -n jenkins jenkins-agent
# Expected: Port 50000/TCP
```

### 🛠️ The Fix

1. **If JNLP Port is Unreachable:**
   Ensure the JNLP service is running and properly exposes port 50000:
   ```bash
   kubectl apply -f k8s/jenkins-service.yaml
   ```

2. **If JCasC Cloud Tunnel is Wrong:**
   Inspect `jcasc/jenkins.yaml` and verify:
   ```yaml
   clouds:
     - kubernetes:
         jenkinsUrl: "http://jenkins.jenkins.svc.cluster.local:8080"
         jenkinsTunnel: "jenkins-agent.jenkins.svc.cluster.local:50000"
   ```
   Apply updated config and reload:
   ```bash
   kubectl create configmap jenkins-casc-config --from-file=jenkins.yaml=jcasc/jenkins.yaml -n jenkins --dry-run=client -o yaml | kubectl apply -f -
   kubectl rollout restart deployment/jenkins -n jenkins
   ```

### ✅ Verification
Trigger a new build. Ephemeral agent pod should transition: `Pending` ➔ `Running` ➔ Jenkins assigns job ➔ Pod terminates upon completion.

---

## 3. Scenario B: Controller CrashLoopBackOff or Init Container Plugin Failure

### 🔴 Symptom
- Controller pod in `CrashLoopBackOff` or `Init:Error` status.
- UI at `http://localhost:8080` is completely unreachable (HTTP 502/Connection Refused).

### 🔍 Cause
- `copy-plugins` init container failed due to plugin dependency conflicts, network timeout downloading from Jenkins update center, or corrupt `plugins.txt`.
- Invalid syntax in `jcasc/jenkins.yaml` causing JCasC parser exception during startup.

### 🩺 Step-by-Step Diagnosis

#### Step 1: Check Init Container Logs
```bash
kubectl logs -n jenkins -l app.kubernetes.io/name=jenkins -c copy-plugins
```
Look for download errors or missing plugin dependencies.

#### Step 2: Check Controller Application Container Logs
```bash
kubectl logs -n jenkins -l app.kubernetes.io/name=jenkins -c jenkins
```
Look for `io.jenkins.plugins.casc.ConfigAsCodeException` indicating an invalid YAML key or indentation error in JCasC.

### 🛠️ The Fix
1. **Fix YAML Syntax in `jcasc/jenkins.yaml`:**
   Validate YAML indentation and update ConfigMap:
   ```bash
   kubectl create configmap jenkins-casc-config --from-file=jenkins.yaml=jcasc/jenkins.yaml -n jenkins --dry-run=client -o yaml | kubectl apply -f -
   kubectl delete pod -n jenkins -l app.kubernetes.io/name=jenkins
   ```

---

## 4. Scenario C: Pipeline Deployment RBAC Permission Denied (403 Forbidden)

### 🔴 Symptom
- Pipeline build fails in `Deploy to Kubernetes Cluster` stage with:
  `Error from server (Forbidden): deployments.apps is forbidden: User "system:serviceaccount:jenkins:jenkins" cannot get resource "deployments" in API group "apps" in the namespace "sample-app"`.

### 🔍 Cause
- The ServiceAccount assigned to the build agent pod lacks RBAC permissions to create/patch Deployments and Services across namespaces.

### 🩺 Step-by-Step Diagnosis
```bash
# Test permissions of the jenkins ServiceAccount directly using kubectl auth
kubectl auth can-i create deployments --as=system:serviceaccount:jenkins:jenkins -n sample-app
kubectl auth can-i create pods --as=system:serviceaccount:jenkins:jenkins -n jenkins
```
If output is `no`, the ClusterRole or ClusterRoleBinding is missing or unlinked.

### 🛠️ The Fix
Apply the unified ClusterRole and ClusterRoleBinding:
```bash
kubectl apply -f k8s/jenkins-rbac.yaml
```

### ✅ Verification
Re-run `kubectl auth can-i create deployments --as=system:serviceaccount:jenkins:jenkins -n sample-app` and confirm output is `yes`.

---

## 5. Scenario D: ImagePullBackOff / ErrImagePull from Local In-Cluster Registry

### 🔴 Symptom
- Pods deployed in `sample-app` enter `ImagePullBackOff` or `ErrImagePull` when attempting to pull custom images built locally.

### 🔍 Cause
- The KinD node's `containerd` daemon cannot resolve the local registry container (`kind-registry:5000` or `localhost:5001`), or the registry container is not connected to the `kind` Docker network bridge.

### 🩺 Step-by-Step Diagnosis
```bash
# 1. Check if registry container is running
docker ps --filter "name=kind-registry"

# 2. Check if registry is connected to the KinD network
docker inspect -f '{{json .NetworkSettings.Networks.kind}}' kind-registry
```

### 🛠️ The Fix
```bash
# Reconnect registry to kind network
docker network connect "kind" "kind-registry" || true

# Verify registry hosting ConfigMap exists in cluster
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:5001"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF
```

---

## 6. Emergency Recovery & Escalation

If the environment is irreparably corrupted during emergency testing:

```bash
# 1. Clean teardown
make down
# or ./scripts/teardown.sh / .\scripts\teardown.ps1

# 2. Fresh zero-state bootstrap
make up
# or ./scripts/bootstrap.sh / .\scripts\bootstrap.ps1
```
