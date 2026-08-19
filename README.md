# 🚀 Vivek Pod Platform Proj - GitOps Kubernetes CI/CD Platform

> **Assessment Submission**: Platform Engineer / SRE Technical Challenge  
> **Author**: Vivek  
> **Environment Support**: Local Host (Linux/Mac/WSL) & Proxmox VE (VMs / Baremetal)

---

## 📌 Executive Overview

**Vivek Pod Platform Proj** is a cloud-native, GitOps-driven CI/CD platform built on Kubernetes. It replaces traditional monolithic Jenkins controllers by introducing:

1. **Ephemeral Agent Pods**: Build workloads execute inside temporary, dynamic multi-container Kubernetes pods (`jnlp` + `builder` sidecars) that spin up on-demand per build job and auto-terminate upon completion.
2. **Zero-UI Configuration**: 100% of Jenkins settings, RBAC permissions, credentials, and pipeline job definitions are managed via **Jenkins Configuration-as-Code (JCasC)** and **Job DSL**.
3. **Zero-Cost Container Registry**: Integrates a local Docker registry on port `5001` directly connected to the KinD network.
4. **Single-Command Setup (`make up`)**: Fully automated prerequisite detection and cluster provisioning.

---

## 🧠 Architectural Design Rationale: JCasC vs. K8s Manifests vs. Helm

> *"There's no single right answer for where the line sits between what belongs in Jenkins config-as-code and what belongs in Kubernetes manifests or Helm values. That's part of what we're actually looking at, so be ready to walk us through why you drew the line where you did."*

### 📐 Where the Line is Drawn

In this architecture, a strict **Separation of Concerns** boundary is established:

```
+-----------------------------------------------------------------------------------------+
|                               DESIGN BOUNDARY MATRIX                                   |
+------------------------------------+----------------------------------------------------+
| Jenkins Config-as-Code (JCasC)     | Kubernetes Manifests & Helm Values                 |
+------------------------------------+----------------------------------------------------+
| • Jenkins System Message & Location| • Application Deployment Specs (Replicas, CPU/Mem) |
| • Authentication (Security Realm)  | • Service Exposure (NodePort, Ingress, Ports)      |
| • Authorization Matrix (RBAC)      | • Application ConfigMaps & Secrets                 |
| • K8s Cloud & Ephemeral Agent Pods | • Application Namespace Definitions (`sample-app`)  |
| • Job DSL Pipeline Seeding         | • Rolling Update & Health Check Policies           |
+------------------------------------+----------------------------------------------------+
```

### 💡 Why This Boundary Was Chosen

#### 1. Decoupling Build Infrastructure (CI) from Application Delivery (CD)
- **JCasC** defines *how builds run* (which agent pods to spawn, what tools are available).
- **Kubernetes Manifests / Helm** define *how applications run* (replica counts, ports, memory limits).
- **Benefit**: Application developers can modify deployment manifests or Helm charts without needing access or changes to the Jenkins JCasC repository.

#### 2. Adherence to GitOps & Immutability
- If the Jenkins controller pod fails or is deleted, applying JCasC reconstructs the entire Jenkins platform in seconds.
- Application state remains untouched inside the Kubernetes cluster (`sample-app` namespace), ensuring zero downtime for running services.

#### 3. Principle of Least Privilege & RBAC Scope
- JCasC configures Jenkins controller security (Admin, Developer, Auditor roles).
- The Jenkins Kubernetes agent ServiceAccount (`jenkins-agent`) is scoped specifically via RoleBinding to perform deployments inside the `sample-app` namespace without possessing ClusterAdmin rights.

#### 4. Environment Portability across Dev, Staging & Production
- Helm values (`helm/sample-app/values.yaml`) allow easy parameterization per target environment (e.g., changing replicas from 2 to 10 in production).
- JCasC remains static regardless of target environment scale.

---

## 🏗️ Platform Architecture

```text
+-----------------------------------------------------------------------------------+
|                            VIVEK POD PLATFORM ARCHITECTURE                        |
+-----------------------------------------------------------------------------------+
|  [ Proxmox VM / Local Host Machine ]                                               |
|       |                                                                           |
|       +--> KinD Kubernetes Cluster ("kind-jenkins")                               |
|               |                                                                   |
|               +--> Namespace: jenkins                                             |
|               |       |--> Jenkins Controller Pod (Port 8080 / NodePort 30080)   |
|               |       |--> Ephemeral Agent Pod (Dynamic per pipeline execution)  |
|               |                 |--> jnlp container (Jenkins Agent)               |
|               |                 |--> builder container (kubectl & tools)         |
|               |                                                                   |
|               +--> Namespace: sample-app                                          |
|                       |--> Vivek Pod Platform Proj (Nginx App / NodePort 30081)  |
|                                                                                   |
|       +--> Local Container Registry ("kind-registry" on Port 5001)                |
+-----------------------------------------------------------------------------------+
```

---

## 👥 Authentication & Matrix RBAC

| Role | Username | Password | Permissions & Access Scope |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin` | `adminpassword123` | Full admin privileges (JCasC, Agent config, Job management, System settings). |
| **Lead Developer**| `developer` | `devpassword123` | Job execution (`Job/Build`), console log viewing, workspace inspect, build trigger. |
| **Auditor** | `auditor` | `auditpassword123` | Read-Only compliance access (`Overall/Read`, `Job/Read`, `View/Read`). |

---

## ⚡ Quick-Start Guide

### 1. One-Command Automated Setup
On any clean Linux machine or Proxmox VM:

```bash
make up
```

This automatically:
- Installs system dependencies (`docker`, `kubectl`, `kind`, `curl`, `make`).
- Provisions the KinD Kubernetes cluster and local Docker registry on port 5001.
- Applies Namespaces (`jenkins`, `sample-app`), RBAC, JCasC, and deploys the platform.

### 2. Accessing Services

- **Jenkins Web UI**: `http://<HOST-IP>:8080` (or `http://localhost:8080`)
- **Vivek Pod Platform Web App**: `http://<HOST-IP>:30081` (or `http://localhost:30081`)

### 3. One-Command Teardown
To remove the cluster and clean up resources:

```bash
make down
```

---

## 📂 Repository Directory Structure

```text
.
├── Makefile                               # Command shortcuts (make up, make down)
├── README.md                              # Main platform documentation & design rationale
├── QuadGen_Round2_K8s_Jenkins_Assessment.docx  # Original assessment specification
├── Proxmox_VM_Step_By_Step_Guide.docx          # Step-by-step Proxmox deployment guide
├── sample-app/                            # Vivek Pod Platform Nginx Application
│   ├── Dockerfile                         # Lightweight Nginx alpine Dockerfile
│   ├── Jenkinsfile                        # Ephemeral agent pod CI/CD pipeline
│   └── index.html                         # Sleek dashboard UI
├── jcasc/                                 # Jenkins Configuration-as-Code
│   ├── jenkins.yaml                       # JCasC definition, RBAC matrix, K8s agent pod specs
│   └── plugins.txt                        # Required Jenkins plugins list
├── k8s/                                   # Kubernetes Manifests
│   ├── namespaces.yaml                    # jenkins & sample-app namespaces
│   ├── jenkins-rbac.yaml                  # Controller & Agent ServiceAccounts & RBAC
│   ├── jenkins-deployment.yaml            # Jenkins Controller deployment & probes
│   ├── jenkins-service.yaml               # Jenkins NodePort 30080 service
│   └── sample-app/                        # Sample app ConfigMap, Deployment & Service (NodePort 30081)
├── helm/                                  # Helm Charts
│   └── sample-app/                        # Helm chart for application deployment
├── kind/                                  # KinD Cluster Configurations
│   └── kind-config.yaml                   # 0.0.0.0 external LAN port bindings
├── scripts/                               # Platform Bootstrap & Teardown
│   ├── bootstrap.sh                       # 1-command installer script
│   └── teardown.sh                        # Cleanup script
└── viveks-poc-folder-attachments/         # Attachment directory for extra POC scripts & guides
    ├── setup_kvm_vm_100.py                # Automated script for Proxmox VM 100
    ├── create_vm_2000.py                 # Automated script for Proxmox VM 2000
    ├── create_template_3000.py            # Automated script for Proxmox Template 3000
    ├── AUTH_AND_RBAC.md                   # Detailed RBAC matrix guide
    ├── PROXMOX_GUIDE.md                   # Proxmox VM & Template guide
    ├── RUNBOOK.md                         # Operational & troubleshooting runbook
    └── SECURITY.md                        # Security posture documentation
```

---

## 📄 License & Assessment Information
Created for **QuadGen Technical Challenge - Engineer II, Platform / SRE**.
