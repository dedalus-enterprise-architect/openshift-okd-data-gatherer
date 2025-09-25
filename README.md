# OpenShift Data Gatherer

End‑user tool to take a clean snapshot of workload controller manifests and node capacity from one or more OpenShift clusters, then produce concise HTML reports for capacity planning and configuration auditing. It intentionally skips live Pod objects: the focus is sizing, configuration consistency, and inventory – not runtime metrics.

---
## 1. What You Get
* A repeatable snapshot (current state only) of selected workload kinds and nodes
* Fast, parallel collection with namespace filtering
* Deterministic normalized manifests (stable for diffing outside this tool)
* Lightweight on-cluster access (read‑only RBAC provided)
* HTML reports (summary, capacity, nodes, container configuration) with automatic highlighting of missing or risky settings

The database always reflects the latest sync; removed objects disappear automatically (no history retention/purging to manage).

---
## 2. Typical Use Cases
| Goal | How |
|------|-----|
| Get an inventory of controllers & their specs | Run `sync`, then `report --type summary` |
| Understand total requested vs limited CPU/RAM | `report --type capacity` |
| Audit container configuration & missing requests/limits | `report --type containers-config` |
| Inspect node sizing and available capacity snapshot | `nodes` command or `report --type nodes` |
| Quickly onboard multiple clusters | Add entries to `config/config.yaml`, run `init` + `sync` per cluster |

---
## 3. Quick Start
1. Create an isolated Python environment (virtual environment or similar).
2. Install the dependencies listed in `requirements.txt`.
3. Copy `config/example-config.yaml` to `config/config.yaml` and edit for your clusters.
4. Run the CLI subcommands in this order for each cluster: `init` → `sync` → `report`.
5. Open the generated HTML report(s) under `clusters/<cluster>/reports/`.

### Basic Usage Example (Single Cluster)
```bash
# Setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure your cluster (edit config/config.yaml with your cluster details)
cp config/example-config.yaml config/config.yaml

# Initialize and sync data for one cluster
python -m data_gatherer.run init --cluster my-cluster
python -m data_gatherer.run sync --cluster my-cluster

# Generate all reports for that cluster
python -m data_gatherer.run report --cluster my-cluster --all

# View the reports
# Reports will be in: clusters/my-cluster/reports/
```

### Multi‑Cluster Examples
```bash
# Initialize every cluster defined in config
python -m data_gatherer.run init --all-clusters

# Sync a subset of clusters in one call
python -m data_gatherer.run sync --cluster prod --cluster staging

# Sync all clusters (parallel per kind inside each cluster)
python -m data_gatherer.run sync --all-clusters

# Generate ALL report types for all clusters
python -m data_gatherer.run report --all-clusters --all

# Generate only capacity report for two clusters
python -m data_gatherer.run report --cluster prod --cluster staging --type capacity

# Show status for all configured clusters
python -m data_gatherer.run status --all-clusters

# List nodes (snapshot) for several clusters
python -m data_gatherer.run nodes --cluster prod --cluster staging
```

### Additional Usage Patterns (Legacy single-cluster style)
```bash
# Daily capacity review (single cluster)
python -m data_gatherer.run sync --cluster prod
python -m data_gatherer.run report --cluster prod --type capacity

# Configuration audit across multiple clusters (single command now)
python -m data_gatherer.run report --cluster prod --cluster staging --type containers-config

# Quick multi-cluster inventory
python -m data_gatherer.run status --all-clusters
python -m data_gatherer.run nodes --all-clusters

# Generate specific reports only
python -m data_gatherer.run report --cluster prod --type summary
python -m data_gatherer.run report --cluster prod --type nodes
```

---
## 4. Configuration Essentials
Create `config/config.yaml`. Each cluster entry chooses ONE authentication method: kubeconfig, direct service account token, or client certificate.

**Authentication Methods:**

1. **Kubeconfig** - Uses existing kubectl configuration
2. **Service Account Token** - Direct token authentication with host/token/ca_file
3. **Client Certificate** - Mutual TLS with cert_file/key_file/ca_file

**Key Configuration Fields:**
* include_kinds – only collect what you need (include `Node` for node sizing)
* ignore_system_namespaces – auto‑skip common system namespaces
* exclude_namespaces – add exact names or wildcards like `sandbox-*`
* parallelism – adjust concurrency (API friendly default `4`)
* write_manifest_files – set to false if you only want the DB + reports

Supported kinds (may safely subset): Deployment, StatefulSet, DaemonSet, Job, CronJob, DeploymentConfig, BuildConfig, Node.

See `config/example-config.yaml` for a concrete template covering kubeconfig and token-based authentication patterns; adapt it rather than copying snippets from this document.

---
## 5. RBAC (One-Time Cluster Prep)
Use the provided read‑only role for a service account. Run the helper script `rbac/setup-rbac.sh` (see that file for usage) to output a configuration snippet containing token and host; place the snippet inside your `config/config.yaml`.

For manual steps or permission details see `rbac/README.md`.

---
## 6. Core Commands & Options
CLI subcommands: init, sync, status, nodes, kinds, report.

### Global
- `--config PATH` (all commands) – Config file (default `config/config.yaml`)

### Multi-Cluster Conventions
- `--cluster NAME` may be repeated (order preserved)
- `--all-clusters` selects every configured cluster (mutually additive with individual flags only in sense you can just use this alone)

### `init`
Initialize storage (creates `clusters/<name>/data.db`).
```bash
python -m data_gatherer.run init --cluster prod
python -m data_gatherer.run init --all-clusters
```

### `sync`
Fetch current manifests + nodes (snapshot overwrite).
```bash
python -m data_gatherer.run sync --cluster prod
python -m data_gatherer.run sync --cluster prod --cluster staging
python -m data_gatherer.run sync --all-clusters
python -m data_gatherer.run sync --cluster prod --kind Deployment --kind Node
```
Options:
- `--kind KIND` (repeatable) – Limit to subset instead of configured `include_kinds`.

### `status`
Show summary counts per cluster.
```bash
python -m data_gatherer.run status --cluster prod
python -m data_gatherer.run status --all-clusters
```

### `nodes`
List node capacity snapshot (JSON output).
```bash
python -m data_gatherer.run nodes --cluster prod
python -m data_gatherer.run nodes --all-clusters
```

### `kinds`
List supported kinds & API group.
```bash
python -m data_gatherer.run kinds
```

### `report`
Generate HTML reports per cluster.
```bash
# Single cluster, one report
python -m data_gatherer.run report --cluster prod --type capacity

# Single cluster, every report type
python -m data_gatherer.run report --cluster prod --all

# Multi-cluster, capacity only
python -m data_gatherer.run report --cluster prod --cluster staging --type capacity

# All clusters, all report types
python -m data_gatherer.run report --all-clusters --all
```
Options:
- `--type NAME` – One of: summary, capacity, nodes, containers-config (default: summary)
- `--all` – Generate every available type (ignores `--type`)
- `--out PATH` – Explicit file path (single-cluster only)
- `--list-types` – Show available report types then exit

Typical flow: `init --all-clusters` → periodic `sync --all-clusters` → `report --all-clusters --all` when you need fresh HTML.

---
## 7. Reports Overview (Summary Only)
Available HTML report types provide inventory, capacity aggregation, container configuration auditing, and node sizing snapshots. Each report includes a concise legend and automatic highlighting for missing or risky configuration.

Full descriptions, use cases, highlighting meanings, and filename conventions are documented in `data_gatherer/reporting/README.md`.



---
## 9. Node Sizing Snapshot
Include `Node` in `include_kinds` to capture per-node capacity + allocatable plus basic attributes (roles, instance type, zone). View with the `nodes` command or nodes report. This is a point‑in‑time view (no historical trend retention).

---
## 10. Operational Tips
* Re-run `sync` any time – it replaces previous data safely.
* Removing a kind from `include_kinds` will cause its historical rows to be cleaned during the next sync.
* If a cluster is unreachable, previously synced kinds stay until successfully re-synced or removed from config.
* Reduce `include_kinds` if API rate limits or large clusters slow collection.

Troubleshooting:
* "Cluster not initialized" → run `init` first.
* Empty nodes output → ensure `Node` is in `include_kinds` and rerun `sync`.
* Missing reports directory → generate at least one report; it will be created automatically.

---
## 11. Security & Safety
* Prefer a dedicated service account with the provided read‑only role.
* Keep `verify_ssl: true`; only disable temporarily for initial testing.

---
## 12. Frequently Asked (FAQ)
**Does it show real-time usage?** No. It shows declared requests/limits and node capacity only.

**Can I add custom resource kinds?** Limit to the listed supported kinds for now; trimming the list is safe.

**Where are raw manifests?** Under `clusters/<cluster>/manifests/<Kind>/` unless `write_manifest_files: false`.

