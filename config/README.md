# Configuration

Configuration reference for `config.yaml` and related credential files.

## Directory Structure
```
config/
├── config.yaml          # Main configuration (required)
├── *.crt / *.pem        # Optional: CA / client certs
└── *.token              # Optional: raw token files (if you store them)
```

## Security & Secrets Handling

* Service account tokens / bearer tokens
* API endpoints
* CA certs / client certs / keys
* Kubeconfig paths

Recommended practices:
* Use **service account token** with least-privilege custom ClusterRole
* Avoid embedding long‑lived user tokens
* Rotate service account tokens yearly
* Keep `verify_ssl: true` in production with a valid CA (supply `ca_file` if needed)

## Configuration Format (`config.yaml`)

### Top-level Structure
```yaml
clusters:            # List of cluster entries (required)
system_namespaces:   # Global system namespace patterns (optional)
logging:             # Logging configuration (optional)
storage:             # Storage configuration (optional)
```

### Cluster Entry Options

Each cluster entry supports either:
* `kubeconfig: /path/to/kubeconfig`
OR
* `credentials: { host, token | username/password | cert_file/key_file, ca_file, verify_ssl }`

Additional per-cluster fields:
* `include_kinds`: list of resource kinds to collect
* `ignore_system_namespaces`: auto-exclude system namespaces (boolean)
* `exclude_namespaces`: additional namespace exclusions (supports wildcards)
* `parallelism`: concurrent workers for data collection

### Authentication Methods

#### Kubeconfig File
```yaml
clusters:
   - name: prod
      kubeconfig: ~/.kube/config
      include_kinds: [Deployment, StatefulSet, DaemonSet, Job, CronJob, DeploymentConfig, Node]
      ignore_system_namespaces: true
      exclude_namespaces: []
      parallelism: 4
```

#### Service Account Token
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

#### Client Certificate
```yaml
clusters:
  - name: secure
    credentials:
      host: https://api.secure.example.com:6443
      cert_file: /secure/client.crt
      key_file: /secure/client.key
      ca_file: /secure/ca.crt
      verify_ssl: true
    include_kinds: [Deployment, StatefulSet, Node]
    ignore_system_namespaces: true
```

### Namespace Filtering
* Set `ignore_system_namespaces: true` to automatically exclude namespaces defined in the global `system_namespaces` list
* Define custom system namespace patterns globally using `system_namespaces` (supports wildcards)
* Add patterns to `exclude_namespaces` for cluster-specific exclusions (e.g. `temp-*`, `sandbox-?`)
* Wildcards are supported for pattern matching in both global and cluster-specific exclusions
* Custom exclusions in `exclude_namespaces` are applied in addition to system namespace filtering

### Complete Example
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

system_namespaces:
  - kube-system
  - kube-public
  - kube-node-lease
  - default
  - openshift
  - openshift-*

logging:
   level: INFO
   format: json

storage:
  base_dir: ./clusters
  write_manifest_files: true
```

## Configuration Variables

### Global System Namespaces
- `system_namespaces`: List of namespace patterns to exclude when `ignore_system_namespaces: true` (supports wildcards like `openshift-*`)

### Logging Options
- `level`: DEBUG, INFO, WARNING, ERROR (default: `INFO`)
- `format`: json or text (default: `json`)

### Storage Options
- `base_dir`: Directory for cluster data storage (default: `clusters`)
- `write_manifest_files`: Write raw manifests to disk (default: `true`)

### Cluster Options
- `name`: Unique cluster identifier (required)
- `include_kinds`: Resource types to collect (default: `[Deployment, StatefulSet, DaemonSet, CronJob, DeploymentConfig, Node]`)
- `ignore_system_namespaces`: Skip system namespaces (default: `true`)
- `exclude_namespaces`: Additional namespace exclusions (supports wildcards)
- `parallelism`: Concurrent collection workers (default: `4`)
