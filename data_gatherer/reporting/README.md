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

### ERROR Conditions (Red highlighting)
- Missing value for CPU requests
- Missing value for Memory requests
- Missing ReadinessProbe

### WARNING Conditions (Yellow highlighting)
- Missing value for CPU limits
- Missing value for Memory limits
- ImagePullPolicy set to Always

### Rule Implementation
Rules are defined in `rules/official_rules.py` and applied through the rules engine (`rules/engine.py`). Each rule specifies:
- Condition logic
- Severity level (ERROR/WARNING)
- Descriptive message

## Usage

Reports are generated using the main data gatherer CLI:

```bash
# Generate all reports for a cluster
python -m data_gatherer.run --cluster my-cluster --report-types capacity,nodes,summary,containers-config

# Generate specific report
python -m data_gatherer.run --cluster my-cluster --report-types capacity
```
