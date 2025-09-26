# Reports

This directory contains report generators for analyzing OpenShift cluster data snapshots. Reports provide capacity analysis and workload configuration insights based on the current cluster state.

## Available Reports

### Capacity Report (`capacity`)
- **Purpose**: Analyze declared CPU/memory requests & limits across controller-managed containers
- **File**: `capacity_report.py`
- **Output**: HTML report with resource aggregation tables + per‑namespace & cluster totals
- **Focus**: Allocation patterns, gaps (missing values), and risk indicators (oversized limits, skewed request/limit ratios)

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
- **File**: `containers_config_report.py`
- **Output**: HTML report with container settings and best practices
- **Focus**: Configuration compliance and optimization recommendations

## Report Layout Standards

All reports follow consistent styling:

- **Legend on top**: Simple, concise legend with small font
- **Consistent style**: Same font, size, and colors across all reports
- **Clear sections**: Organized information hierarchy
- **HTML output**: Web-viewable format for easy sharing

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
