# 🛡️ SECURITY ARCHITECTURE & HARDENING GUIDE

> **Environment:** In-Cluster Jenkins Controller + Ephemeral Kubernetes Agent Pods  
> **Security Baseline:** CIS Kubernetes Benchmark & Jenkins Security Best Practices  

---

## 1. Identity & Least Privilege RBAC

| Component | ServiceAccount | Namespace Scope | Allowed Verbs / Resources |
|---|---|---|---|
| **Jenkins Controller** | `jenkins-controller` | `jenkins` only | `pods`, `pods/exec`, `pods/log`, `events`, `secrets`, `configmaps` |
| **Ephemeral Build Agent** | `jenkins-agent` | `sample-app` only | Deployments, ReplicaSets, Services in `sample-app` namespace |

**Key Protection:** Ephemeral agents have **zero permissions** in the `jenkins` controller namespace or `kube-system`, preventing container breakout to cluster takeover.

---

## 2. Pod & Container Security Contexts

All controller and agent pods enforce the following constraints:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
```

And container level hardening:
```yaml
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
```

---

## 3. Jenkins Controller Security (JCasC)

1. **Matrix-Based Authorization (`projectMatrix`):**
   - Disables anonymous write permissions.
   - Enforces granular role-based permissions (`Overall/Administer`, `Job/Build`, `Job/Read`).
2. **Remoting CLI Disabled:**
   - Mitigates CVEs related to unauthenticated Jenkins CLI remoting deserialization.
3. **Legacy API Tokens Disabled:**
   - Prevents generation of unrevokable long-lived legacy tokens.
4. **Agent Isolation:**
   - `numExecutors: 0` on the master controller prevents any build code from running on the controller filesystem.
