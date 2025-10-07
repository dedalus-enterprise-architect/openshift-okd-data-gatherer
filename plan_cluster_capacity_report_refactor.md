# Cluster Capacity Report Refactor Plan

## 1. Discard Old Cluster Capacity Report
- Remove `data_gatherer/reporting/cluster_capacity_report.py` and related registration.
- Remove any references to the old cluster-capacity report in documentation and CLI help.

## 2. Rename Current Container-Capacity Report to Cluster-Capacity
- Rename `data_gatherer/reporting/container_capacity_report.py` to `cluster_capacity_report.py`.
- Update class name and registration to `ClusterCapacityReport`.
- Update all internal references, imports, and registration decorators.

## 3. Update CLI Commands
- Update CLI to use `cluster-capacity` as the report type.
- Remove support for the old `container-capacity` switch.
- Ensure CLI help and argument parsing reflect the new report name and options.

## 4. Discard Unneeded Tests and Refactor Existing Ones for New Report Structure
- Remove tests for the old cluster-capacity report.
- Rename and refactor tests for container-capacity to match new cluster-capacity report structure and naming.
- Ensure all tests validate the new unified report layout and sections.

## 5. Update All References in Documentation with Current Reports and CLI Switches
- Update `README.md` and all documentation files to reference only the new cluster-capacity report.
- Update report descriptions, CLI usage examples, and legend sections to match the new report structure and naming.
- Remove any mention of the old report or switches.

---
This plan ensures a clean migration to a unified cluster capacity report, with consistent naming, CLI usage, and documentation. All legacy code and references will be removed or updated for clarity and maintainability.
