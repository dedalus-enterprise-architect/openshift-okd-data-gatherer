# Configuration

Configuration reference for the OpenShift Resource Analyzer. RBAC assets have been moved to the dedicated `rbac/` directory.

## Contents
1. Overview
2. Directory Structure
3. Security & Secrets Handling
4. Application Configuration (`config.yaml`)
5. Cluster Entry Examples (kubeconfig / credentials)
6. Namespace Exclusions & Kind Selection
7. Example `config.yaml` snippet
8. RBAC Reference Location

---

## 1. Overview
The analyzer gathers workload controller manifests (Deployments, StatefulSets, DaemonSets, Jobs, CronJobs, DeploymentConfigs, optional BuildConfigs) and node capacity data. It does not fetch live Pod objects. Data is stored in a file-based SQLite DB under `clusters/<name>/` with normalized manifests and retention for deleted workloads.

## 2. Directory Structure
```
config/
├── config.yaml          # Main configuration (required)
├── *.crt / *.pem        # Optional: CA / client certs
└── *.token              # Optional: raw token files (if you store them)

rbac/
├── openshift-resource-analyzer-cluster-role.yaml          # ClusterRole (read-only)
├── openshift-resource-analyzer-cluster-role-binding.yaml  # Binding
├── setup-rbac.sh                                          # Setup script
└── README.md                                              # RBAC documentation
```

## 3. Security & Secrets Handling
🔒 The entire `config/` directory is **gitignored** – do not remove that protection. Treat contents as sensitive:
* Service account tokens / bearer tokens
* API endpoints
* CA certs / client certs / keys
* Kubeconfig paths

Recommended practices:
* Use **service account token** with least-privilege custom ClusterRole (provided).
* Avoid embedding long‑lived user tokens.
* Rotate service account tokens yearly (script uses 8760h duration).
* Keep `verify_ssl: true` in production with a valid CA (supply `ca_file` if needed).

## 4. Application Configuration (`config.yaml`)
Top-level keys:
* `clusters`: list of cluster entries
* `logging`: level & format (json|text)
* `storage`: base_dir & deleted retention days

Each cluster entry supports either:
* `kubeconfig: /path/to/kubeconfig`
OR
* `credentials: { host, token | username/password | cert_file/key_file, ca_file, verify_ssl }`

Additional per-cluster fields:
* `include_kinds`: list of kinds (must match tool's supported static map)
* `ignore_system_namespaces`: auto-exclude common kube/openshift namespaces
* `exclude_namespaces`: extra exclusions (supports wildcards)
* `parallelism`: concurrent kind fetch workers

## 5. Cluster Entry Examples
### a. Kubeconfig
```yaml
clusters:
   - name: prod
      kubeconfig: ~/.kube/config
      include_kinds: [Deployment, StatefulSet, DaemonSet, Job, CronJob, DeploymentConfig, Node]
      ignore_system_namespaces: true
      exclude_namespaces: []
      parallelism: 4
```

### b. Service Account Token
```yaml
clusters:
   - name: staging
      credentials:
         host: https://api.staging.example.com:6443
         token: "<sa-bearer-token>"
         verify_ssl: true
         ca_file: /etc/ssl/certs/staging-ca.crt  # if custom CA
      include_kinds: [Deployment, StatefulSet, DaemonSet, Job, CronJob, DeploymentConfig, Node]
      ignore_system_namespaces: true
      exclude_namespaces: []
```

### c. Client Certificate
```yaml
clusters:
   - name: hardened
      credentials:
         host: https://api.secure.example.com:6443
         cert_file: /secure/client.crt
         key_file: /secure/client.key
         ca_file: /secure/ca.crt
         verify_ssl: true
      include_kinds: [Deployment, StatefulSet, Node]
      ignore_system_namespaces: true
```

## 6. Namespace Exclusions & Kind Selection
* Set `ignore_system_namespaces: true` to automatically exclude core kube/openshift system namespaces.
* Add patterns (e.g. `temp-*`, `sandbox-?`) to `exclude_namespaces` – wildcards are parsed into pattern vs exact matching.
* Remove kinds you do not need to minimize API calls and storage.

## 7. Example Minimal `config.yaml`
```yaml
clusters:
   - name: prod-cluster
      credentials:
         host: https://api.cluster.example.com:6443
         token: "eyJhbGc..."
         verify_ssl: false  # set true with proper CA
      include_kinds: [Deployment, StatefulSet, DaemonSet, Job, CronJob, DeploymentConfig, Node]
      ignore_system_namespaces: true
      exclude_namespaces: []
      parallelism: 4

logging:
   level: INFO
   format: json

storage:
   base_dir: ./clusters
   keep_deleted_days: 30
```

---
## 8. RBAC Reference Location
RBAC manifests & detailed permissions documentation have moved to `rbac/README.md`.

For advanced usage & feature roadmap see project root `README.md`.
