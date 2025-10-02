import os
import tempfile
import pytest
from data_gatherer.reporting.cluster_capacity_report import ClusterCapacityReport
from data_gatherer.persistence.db import WorkloadDB

def test_cluster_capacity_report_excel(tmp_path):
    # Setup: create a minimal DB with fake data
    db_path = tmp_path / "test.db"
    db = WorkloadDB(str(db_path))
    # Insert minimal node and workload data
    cur = db._conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS node_capacity (
            cluster TEXT, node_name TEXT, cpu_allocatable TEXT, memory_allocatable TEXT, cpu_capacity TEXT, memory_capacity TEXT, node_role TEXT, deleted INTEGER DEFAULT 0, first_seen TEXT, last_seen TEXT
        )
    """)
    cur.execute("""
        INSERT INTO node_capacity (cluster, node_name, cpu_allocatable, memory_allocatable, cpu_capacity, memory_capacity, node_role, deleted, first_seen, last_seen)
        VALUES ('testcluster', 'n1', '2000', '4096', '2000', '4096', 'worker', 0, '2025-10-02T00:00:00Z', '2025-10-02T00:00:00Z')
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workload (
            cluster TEXT, kind TEXT, namespace TEXT, name TEXT, api_version TEXT, manifest_json TEXT, manifest_hash TEXT, deleted INTEGER DEFAULT 0, first_seen TEXT, last_seen TEXT
        )
    """)
    manifest = '{"kind":"Deployment","spec":{"replicas":2,"template":{"spec":{"containers":[{"name":"c1","resources":{"requests":{"cpu":"500m","memory":"256Mi"},"limits":{"cpu":"1000m","memory":"512Mi"}}}]}}}}'
    cur.execute("""
        INSERT INTO workload (cluster, kind, namespace, name, api_version, manifest_json, manifest_hash, deleted, first_seen, last_seen)
        VALUES ('testcluster', 'Deployment', 'ns1', 'w1', 'apps/v1', ?, 'dummyhash', 0, '2025-10-02T00:00:00Z', '2025-10-02T00:00:00Z')
    """, (manifest,))
    db._conn.commit()

    # Generate Excel report
    out_path = tmp_path / "cluster_capacity_report.xlsx"
    report = ClusterCapacityReport()
    report.generate(db, 'testcluster', str(out_path), format='excel')
    assert os.path.exists(out_path)

    # Validate Excel file contents
    from openpyxl import load_workbook
    wb = load_workbook(str(out_path))
    ws = wb.active
    # Check title
    assert ws.title == "Cluster Capacity Report"
    # Check headers
    headers = [cell.value for cell in ws[3]]
    assert headers[:7] == [
        "Namespace", "CPU Requests (m)", "Memory Requests (Mi)",
        "CPU Limits (m)", "Memory Limits (Mi)", "% CPU allocated on Cluster", "% Memory allocated on Cluster"
    ]
    # Check that totals row exists in any row
    found_totals = False
    print('Excel rows:')
    for row in ws.iter_rows():
        print([str(cell.value) for cell in row])
        if any(str(cell.value).lower().strip() == "totals" for cell in row if cell.value):
            found_totals = True
            break
    assert found_totals
    # Check summary table headers
    summary_headers = [cell.value for cell in ws[ws.max_row-4]]
    assert summary_headers[:5] == [
        "Scope", "CPU (m)", "CPU % Allocatable", "Memory (Mi)", "Memory % Allocatable"
    ]
    wb.close()
