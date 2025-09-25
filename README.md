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

### Basic Usage Example
```bash
# Setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure your cluster (edit config/config.yaml with your cluster details)
cp config/example-config.yaml config/config.yaml

# Initialize and sync data for a specific cluster
python -m data_gatherer.run init --cluster my-cluster
python -m data_gatherer.run sync --cluster my-cluster

# Generate reports
python -m data_gatherer.run report --cluster my-cluster --type all

# View the reports
# Reports will be in: clusters/my-cluster/reports/
```

### Common Usage Patterns
```bash
# Daily capacity review
python -m data_gatherer.run sync --cluster prod
python -m data_gatherer.run report --cluster prod --type capacity

# Configuration audit across all clusters (requires multiple commands)
for cluster in prod staging; do
  python -m data_gatherer.run sync --cluster $cluster
  python -m data_gatherer.run report --cluster $cluster --type containers-config
done

# Quick cluster inventory
python -m data_gatherer.run status --cluster staging
python -m data_gatherer.run nodes --cluster staging

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
## 6. Core Commands (Most Users Only Need These)
Available CLI subcommands: init, sync, status, nodes, kinds, report.

### Global Options
- `--config PATH` - Custom configuration file path (default: config/config.yaml)
- `--help` - Show help message and exit

### Command Details

#### `init` - Initialize cluster data directories
```bash
python -m data_gatherer.run init --cluster CLUSTER
```
- `--cluster CLUSTER` - Target cluster name (required)

#### `sync` - Sync workload data from clusters
```bash
python -m data_gatherer.run sync --cluster CLUSTER [--kinds KIND1,KIND2,...]
```
- `--cluster CLUSTER` - Target cluster name (required)
- `--kinds KIND1,KIND2,...` - Override included resource kinds for this sync

#### `status` - Show cluster sync status
```bash
python -m data_gatherer.run status --cluster CLUSTER
```
- `--cluster CLUSTER` - Target cluster name (required)

#### `nodes` - Display node information
```bash
python -m data_gatherer.run nodes --cluster CLUSTER [--format FORMAT]
```
- `--cluster CLUSTER` - Target cluster name (required)
- `--format FORMAT` - Output format: json, table (default: table)

#### `kinds` - List supported resource kinds
```bash
python -m data_gatherer.run kinds
```

#### `report` - Generate HTML reports
```bash
python -m data_gatherer.run report --cluster CLUSTER [--type TYPE] [--output-dir DIR]
```
- `--cluster CLUSTER` - Target cluster name (required)
- `--type TYPE` - Report type: summary, capacity, nodes, containers-config, all (default: all)
- `--output-dir DIR` - Custom output directory (default: clusters/<cluster>/reports/)

Typical flow per cluster: init → sync (optionally with repeated sync runs) → report (one or all types).

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

