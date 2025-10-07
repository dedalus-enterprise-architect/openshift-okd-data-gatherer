# Core logic

This document summarizes the logic of data extraction, conditional choices, rules evaluation, and math calculations for all major reports in the OpenShift OKD Data Gatherer tool.

## 1. Data Extraction

| Report Type           | Extraction Source/Method                | Filtering Applied                | Conditional Choices |
|---------------------- |-----------------------------------------|----------------------------------|---------------------|
| summary               | WorkloadDB, all workloads               | None (all resources included)     | None                |
| cluster-capacity      | WorkloadDB, CONTAINER_WORKLOAD_KINDS    | Includes 0-replica resources      | If DaemonSet, use worker node count (or 0 if targeting infra/master); else if replica missing, default to 1; else use actual (can be 0) |
| containers-config     | WorkloadDB, CONTAINER_WORKLOAD_KINDS    | Includes 0-replica resources      | If DaemonSet, use worker node count (or 0 if targeting infra/master); else use actual (can be 0) |
| nodes                 | NodeDB, all nodes                       | None (all nodes included)         | None                |

## 2. Rules of evaluation

| Rule Name                | Applies To Column(s)         | Severity      | Condition (cell_value)         |
|------------------------- |-----------------------------|--------------|-------------------------------|
| MissingCpuRequestRule    | CPU_req_m                   | ERROR_MISS   | None, '', '-', 'N/A'          |
| MissingMemoryRequestRule | Mem_req_Mi                  | ERROR_MISS   | None, '', '-', 'N/A'          |
| MissingCpuLimitRule      | CPU_lim_m                   | WARNING_MISS | None, '', '-', 'N/A'          |
| MissingMemoryLimitRule   | Mem_lim_Mi                  | WARNING_MISS | None, '', '-', 'N/A'          |
| ReadinessProbeMissingRule| readinessProbe              | ERROR_MISS   | None, '', '-', 'N/A'          |
| ImagePullPolicyAlwaysRule| imagePullPolicy             | WARNING_MISCONF| 'Always'                     |
| Requests < 20% Limits    | CPU/Mem requests vs limits  | WARNING_MISCONF| req <= 0.2 * lim             |
| Limits > node allocatable| CPU/Mem limits vs node allocatable | ERROR_MISCONF | lim > node allocatable      |

- Rules are evaluated per cell using the rules engine, which applies the highest severity rule triggered.
- 0 values are now treated as valid, not missing.


## 3. Math calculations

| Report Type           | Calculation Logic                                      | Aggregation Scope |
|---------------------- |-------------------------------------------------------|-------------------|
| cluster-capacity      | req/lim * replicas, totals per namespace/cluster       | Per container, namespace, cluster |
| containers-config     | No math, configuration listing only                    | Per container     |
| summary               | Counts, basic stats                                   | Per cluster       |
| nodes                 | Allocatable, capacity, totals (uses node allocatable)  | Per node, cluster |

**Node Allocatable Usage:**
- All capacity calculations use node allocatable resources (capacity minus system-reserved and eviction thresholds) for accuracy.

**DaemonSet Calculation Logic:**
- For DaemonSets, replicas = number of worker nodes (unless nodeSelector targets infra/master, then replicas = 0)
- Per-pod resources are multiplied by replicas for total resource consumption
- NodeSelector filtering ensures only workloads running on worker nodes are included in worker capacity calculations

### Example calculation (cluster-capacity):
- CPU_req_m_total = CPU_req_m * replicas
- Mem_lim_Mi_total = Mem_lim_Mi * replicas
- Aggregates: sum across all containers, then per namespace, then cluster-wide

### Rules engine severity order
| Severity         | Description                       |
|------------------|-----------------------------------|
| ERROR_MISCONF    | Wrong value/parameter set         |
| ERROR_MISS       | Required value/parameter missing  |
| WARNING_MISCONF  | Value/parameter should be re-eval |
| WARNING_MISS     | Recommended value/parameter miss  |
| INFO             | Informational                     |
| NONE             | No issue                          |

