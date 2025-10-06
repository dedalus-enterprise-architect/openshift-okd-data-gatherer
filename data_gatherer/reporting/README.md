# Reports

This directory contains report generators for analyzing OpenShift cluster data snapshots. Reports provide capacity analysis and workload configuration insights based on the current cluster state.


## Available Reports

| Report Type            | File                          | Output Format | Purpose/Focus                                                                 |
|------------------------|-------------------------------|--------------|------------------------------------------------------------------------------|
| summary                | summary_report.py             | HTML         | High-level cluster overview, workload counts, node info                       |
| container-capacity     | container_capacity_report.py  | HTML, Excel  | Per-container resource requests/limits, allocation patterns, risk indicators   |
| cluster-capacity       | cluster_capacity_report.py    | HTML, Excel  | Namespace/cluster-level resource demand, allocatable vs requested, hotspots    |
| containers-config      | containers_config_report.py   | HTML         | Detailed container configuration, compliance, optimization recommendations    |
| nodes                  | nodes_report.py               | HTML         | Node details, infrastructure capacity overview                                |

---

## Enhanced Worker Node Capacity Evaluation

All capacity reports (cluster-capacity, container-capacity, and containers-config) have been enhanced to provide accurate evaluation of resources available on worker nodes and consumed by workloads:

### Worker Node Identification
- **Enhanced Logic**: Worker nodes are identified using multiple methods:
  - Explicit 'worker' role label
  - Nodes without master/infra roles (to capture nodes with custom or missing role labels)
- This ensures all worker nodes are counted, even with non-standard labeling

### Workload Coverage
- **All Workload Types**: Includes Deployments, StatefulSets, DaemonSets, Jobs, CronJobs, and DeploymentConfigs
- **DaemonSet Handling**: 
  - DaemonSets are correctly counted as running one pod per eligible worker node
  - DaemonSets targeting infra or master nodes (via nodeSelector) show 0 replicas for worker capacity
  - This applies to all three reports: cluster-capacity, container-capacity, and containers-config
- **Node Placement**: Workloads targeting master or infra nodes via nodeSelector are excluded from worker node calculations

### Resource Calculations
- **Allocatable Values**: Uses node allocatable resources (already accounts for system-reserved and eviction thresholds)
- **OpenShift Formula**: Allocatable = Capacity - system-reserved - eviction-thresholds
- **Replica Accuracy**: 
  - Properly handles zero-replica deployments
  - Scales DaemonSets per worker node count
  - Shows correct total resource consumption (per-pod × replicas)

### Report-Specific DaemonSet Display
- **cluster-capacity**: Shows aggregated totals per namespace including DaemonSet resources
- **container-capacity**: Shows per-container resources with replica count and total calculations
- **containers-config**: Shows replica count for capacity planning and configuration review

### Benefits
- More accurate capacity utilization percentages
- Better identification of worker node resource pressure
- Correct accounting for system daemons and infrastructure workloads
- Improved capacity planning insights across all reports

---

## Cell Formatting Rules

Reports apply a unified rules engine to highlight configuration quality issues. Each cell is evaluated against the active rule set and may receive one of the severity classes below.

### Severity & Visual Encoding
| Category | Style | Meaning |
|----------|-------|---------|
| ERROR_MISS | Red background | Required value or parameter is missing |
| WARNING_MISS | Yellow background | Recommended value or parameter is missing |
| ERROR_MISCONF | Red text | Wrong value or parameter set |
| WARNING_MISCONF | Orange text | Value or parameter set should be re-evaluated |

### Implemented Rules

Legend: 🟥 / 🔴 = error, 🟨 / 🟧 = warning (background-like vs text-like categories).

| # | Rule | Severity | Emoji |
|---|-------|----------|-------|
| 1 | Missing CPU request | ERROR_MISS | 🟥 |
| 2 | Missing Memory request | ERROR_MISS | 🟥 |
| 3 | Missing CPU limit | WARNING_MISS | 🟨 |
| 4 | Missing Memory limit | WARNING_MISS | 🟨 |
| 5 | Readiness probe missing / not configured | ERROR_MISS | 🟥 |
| 6 | ImagePullPolicy set to Always | WARNING_MISCONF | 🟧 |
| 7 | CPU or Memory requests value is lower or equal than 20% of its corresponding limits | WARNING_MISCONF | 🟧 |
| 8 | CPU limits value is higher than the total amount of CPUs of the smallest cluster worker node | ERROR_MISCONF | 🔴 |
| 9 | Memory limits value is higher than the total amount of RAM of the smallest cluster worker node | ERROR_MISCONF | 🔴 |

### Rule Implementation
Rules are defined in `rules/official_rules.py` and dispatched through the rules engine (`rules/engine.py`). The renderer applies the CSS class corresponding to the highest severity rule triggered for that cell.

## Usage

Reports are generated via the main CLI `report` subcommand. You can target one or many clusters.

### Report Command Output & Combination Rules

The `report` command now supports flexible combinations of `--all`, `--format`, and `--out`:

| Scenario | Example | Behavior |
|----------|---------|----------|
| Single cluster, single report, default format | `report --cluster prod --type summary` | Writes to `clusters/prod/reports/<prefix><timestamp>.html` |
| Single cluster, single report, explicit file | `report --cluster prod --type container-capacity --format excel --out /tmp/cc.xlsx` | Writes exactly to `/tmp/cc.xlsx` |
| Single cluster, all reports (HTML default) | `report --cluster prod --all` | Generates every registered type (one file per type) into `clusters/prod/reports/` |
| Single cluster, all reports, override format & custom dir | `report --cluster prod --all --format excel --out /tmp/prod-reports` | Creates directory if missing; one Excel per report type |
| Multi-cluster, single report | `report --cluster prod --cluster staging --type summary` | One file per cluster under each cluster's `reports/` dir |
| Multi-cluster, all reports to shared dir | `report --all-clusters --all --out /tmp/all-reports` | One file per (cluster,type) in given directory |
| Multi-cluster, format override | `report --all-clusters --all --format excel --out ./reports-all` | Forces Excel where supported; skips format override where not supported |

#### `--out` Semantics
* If multiple outputs will be produced (because of `--all` and/or multiple clusters), `--out` must point to a directory (it will be created if absent).
* If only one output will be produced, `--out` may be either a file path or a directory.
* When a directory is used for multiple outputs, filenames follow:
	` <prefix><report-type>-<cluster>-<timestamp>.<ext>`
	(Example: `summary-summary-prod-20250101T101500.html`)

#### `--format` Override
* Applies globally to all targeted report types for the invocation.
* If a report does not support the requested format, it falls back to its first supported format and logs a notice (the run continues).

#### Examples
Generate all reports for a single cluster into a custom directory in Excel:
```bash
python -m data_gatherer.run report --cluster prod --all --format excel --out ./excel-reports
```
Generate all reports for every configured cluster into a shared directory:
```bash
python -m data_gatherer.run report --all-clusters --all --out /tmp/all-reports
```
Single summary report for two clusters, forcing HTML into default per-cluster locations:
```bash
python -m data_gatherer.run report --cluster prod --cluster staging --type summary --format html
```
Explicit single output file path:
```bash
```

### Getting Help

Use the custom `help` command to list all available commands or get detailed help for a specific command:

```bash
# List all available commands
python -m data_gatherer.run help

# Show help for a specific command (e.g., report)
python -m data_gatherer.run help report
```
