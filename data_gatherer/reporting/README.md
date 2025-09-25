# Reports

This directory contains report generators for analyzing OpenShift cluster data snapshots. Reports provide capacity analysis and workload configuration insights based on the current cluster state.

## Available Reports

### Capacity Report (`capacity`)
- **Purpose**: Analyze resource requests and limits across workloads
- **File**: `capacity_report.py`
- **Output**: HTML report with resource utilization tables
- **Focus**: CPU and memory allocation analysis for containers

### Nodes Report (`nodes`)
- **Purpose**: Display cluster node information and capacity
- **File**: `nodes_report.py`
- **Output**: HTML report with node details and resource capacity
- **Focus**: Infrastructure capacity overview

### Summary Report (`summary`)
- **Purpose**: High-level cluster overview
- **File**: `summary_report.py`
- **Output**: HTML summary with workload counts and node information
- **Focus**: Quick cluster health snapshot

### Container Configuration Report (`containers-config`)
- **Purpose**: Detailed container configuration analysis
- **File**: `unified_containers_report.py`
- **Output**: HTML report with container settings and best practices
- **Focus**: Configuration compliance and optimization recommendations

## Report Layout Standards

All reports follow consistent styling:

- **Legend on top**: Simple, concise legend with small font
- **Consistent style**: Same font, size, and colors across all reports
- **Clear sections**: Organized information hierarchy
- **HTML output**: Web-viewable format for easy sharing

## Cell Formatting Rules

Reports apply visual indicators based on configuration quality:

### Severity & Visual Encoding
| Category | Style | Meaning |
|----------|-------|---------|
| ERROR_MISS | Red background | Required value missing (requests, readiness probe) |
| WARNING_MISS | Yellow background | Recommended value missing (limits) |
| ERROR_MISCONF | Red text | Value likely invalid or too large (limit >= smallest node) |
| WARNING_MISCONF | Orange text | Suspicious configuration (request far below limit, image pull policy Always) |

### Implemented Rules
- Missing CPU request (ERROR_MISS)
- Missing Memory request (ERROR_MISS)
- Missing CPU limit (WARNING_MISS)
- Missing Memory limit (WARNING_MISS)
- Readiness probe missing (ERROR_MISS)
- ImagePullPolicy = Always (WARNING_MISCONF)
- Request <= 20% of corresponding limit (WARNING_MISCONF)
- CPU/Memory limit >= smallest node capacity (ERROR_MISCONF)

### Rule Implementation
Rules are defined in `rules/official_rules.py` and applied through the rules engine (`rules/engine.py`). Each rule specifies condition logic, severity category, and message.

## Usage

Reports are generated via the main CLI `report` subcommand. You can target one or many clusters.

```bash
# List available report types
python -m data_gatherer.run report --list-types

# Single cluster: generate every report type
python -m data_gatherer.run report --cluster my-cluster --all

# Single cluster: only capacity report
python -m data_gatherer.run report --cluster my-cluster --type capacity

# Two clusters: capacity report each
python -m data_gatherer.run report --cluster prod --cluster staging --type capacity

# All configured clusters: all report types
python -m data_gatherer.run report --all-clusters --all

# Explicit output path (single cluster only)
python -m data_gatherer.run report --cluster prod --type summary --out /tmp/prod-summary.html
```
