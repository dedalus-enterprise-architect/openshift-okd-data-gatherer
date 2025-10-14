
# OpenShift Data Gatherer

OpenShift Data Gatherer is a snapshot tool for collecting controller manifests and node capacity from OpenShift clusters. It produces concise reports for capacity planning and configuration auditing. The focus is on sizing, configuration consistency, and inventory — not live metrics.

---

## 1. How Does It Work?

The data gatherer follows a simple workflow to collect, store, and report cluster data:

1. **Initialization**: Set up local storage for each cluster using the `init` command. This creates a dedicated database for storing snapshots.
2. **Configuration**: Define clusters and authentication in `config/config.yaml`. Optionally, set up read-only RBAC in your cluster for secure access.
3. **Data Collection (Sync)**: Run the `sync` command to connect to the cluster and fetch manifests and node capacity. Only the current state is collected—no historical data is retained.
4. **Snapshot Storage**: The latest cluster state is saved in the local database. Removed objects are automatically purged on each sync.
5. **Reporting**: Generate HTML or Excel reports using the `report` command. Reports cover capacity, configuration, and inventory, not live metrics. Output files are saved in `clusters/<cluster>/reports/`.
6. **Review & Audit**: Open generated reports for analysis, capacity planning, and configuration auditing.

This workflow ensures repeatable, up-to-date snapshots and reports for OpenShift/OKD clusters, supporting inventory, sizing, and compliance needs.

---
## 2. Typical Use Cases
| Goal | How |
|------|-----|
| Get an inventory of controllers & specs | Run `sync`, then `report --type summary` |
| See per-container CPU/RAM requests/limits + namespace aggregation | `report --type cluster-capacity` |
| See namespace/cluster-level resource demand vs allocatable | `report --type cluster-capacity` |
| Audit container configuration & missing requests/limits | `report --type containers-config` |
| Inspect node sizing and available capacity | `nodes` command or `report --type nodes` |
| Onboard multiple clusters | Add entries to `config/config.yaml`, run `init` + `sync` per cluster |

---
## 3. Quick Start
1. (If not already) Clone this repository and `cd` into it.
2. Create & activate a Python virtual environment.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy the sample config: `cp config/example-config.yaml config/config.yaml` ([`config/example-config.yaml`](config/example-config.yaml)).
5. Edit `config/config.yaml` with at least one cluster (choose ONE auth method per cluster).
6. (Optional, but recommended first time) Set up read‑only RBAC in the cluster; see Section 5 and run `rbac/setup-rbac.sh` to obtain token/host values, then update the config.
7. Initialize storage for your cluster(s): `python -m data_gatherer.run init --cluster my-cluster` (or `--all-clusters`).
8. Collect a snapshot: `python -m data_gatherer.run sync --cluster my-cluster`.
9. Generate reports: `python -m data_gatherer.run report --cluster my-cluster --all`.
10. Open the reports in [`clusters/my-cluster/reports/`](clusters/) (HTML) or your chosen output path (Excel).


### Usage Examples

Initialize storage:
```bash
python -m data_gatherer.run init --cluster my-cluster
```
Sync cluster data:
```bash
python -m data_gatherer.run sync --cluster my-cluster
```
Generate all reports:
```bash
python -m data_gatherer.run report --cluster my-cluster --all
```
Generate a specific report in Excel format:
```bash
python -m data_gatherer.run report --cluster my-cluster --type cluster-capacity --format excel --out /tmp/capacity_report.xlsx
```
List node capacity:
```bash
python -m data_gatherer.run nodes --cluster my-cluster
```

---
## 4. Supported Resource Kinds
The following Kubernetes/OpenShift resource kinds are supported for snapshot and reporting:

- Deployment
- StatefulSet
- DaemonSet
- Job
- CronJob
- DeploymentConfig
- BuildConfig
- Node

---
## 5. Configuration
See [`config/README.md`](config/README.md) for configuration instructions, authentication methods, and example templates.

### Namespace-Scoped Mode (Optional)
If you cannot grant a ClusterRole, you can operate in a restricted mode by setting `namespace_scoped: true` and providing an `include_namespaces` list per cluster. In this mode only those namespaces are queried, and cluster-scoped kinds (e.g. `Node`) are skipped automatically. Capacity sections that depend on node data will show N/A markers. See the RBAC section below and the config docs for details.

---
## 6. RBAC (One-Time Cluster Prep)
You can choose between two RBAC models:

| Mode | Scripts / Files | When to Use | Notes |
|------|------------------|-------------|-------|
| Cluster-scoped | `rbac/setup-rbac-cluster.sh`, `data-gatherer-clusterrole*.yaml` | You can grant broad read-only access | Includes Node + cluster-wide discovery |
| Namespace-scoped | `rbac/setup-rbac-namespace.sh`, `data-gatherer-role-namespace*.yaml` | Strict least-privilege environments | Only listed namespaces; Nodes skipped |

Cluster Mode: run `rbac/setup-rbac-cluster.sh` and copy the emitted config snippet (`namespace_scoped: false`).

Namespace Mode: run `rbac/setup-rbac-namespace.sh ns1 ns2 ...` and copy the snippet (contains `namespace_scoped: true` and `include_namespaces`).

For full permission manifests and manual steps see [`rbac/README.md`](rbac/README.md).

---
## 7. Core Commands & Options
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

### Report Types
Use `python -m data_gatherer.run report --list-types` to see all available types.
For detailed descriptions of each report, output formats, and legend, see [`data_gatherer/reporting/README.md`](data_gatherer/reporting/README.md).

> **See also:** [Core logic and rules summary](core_logic.md) — for detailed tables on extraction, filtering, rules, and math logic used in all reports.

## 8. Node Sizing Snapshot
Include `Node` in `include_kinds` (cluster-scoped mode only) to capture per-node capacity and attributes. In namespace-scoped mode node data is intentionally not collected; related report sections will show N/A.

## 9. Operational Tips
* Re-run `sync` any time—it safely replaces previous data.
* Removing a kind from `include_kinds` will clean its rows on next sync.
* If a cluster is unreachable, previously synced kinds stay until re-synced or removed.
* Reduce `include_kinds` if API rate limits or large clusters slow collection.

Troubleshooting:
* "Cluster not initialized" → run `init` first.
* Empty nodes output → ensure `Node` is in `include_kinds` and rerun `sync`.
* Missing reports directory → generate at least one report; it will be created automatically.

---
## 10. Security & Safety
* Use a dedicated service account with the provided read-only role.
* Keep `verify_ssl: true`; only disable temporarily for initial testing.

---
## 11. FAQ
**Does it show real-time usage?** No, only declared requests/limits and node capacity.

**Can I add custom resource kinds?** Limit to the listed supported kinds for now.

**Where are raw manifests?** Under [`clusters/<cluster>/manifests/<Kind>/`](clusters/) unless `write_manifest_files: false`.

