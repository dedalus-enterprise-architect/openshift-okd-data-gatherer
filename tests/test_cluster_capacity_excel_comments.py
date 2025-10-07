"""Updated tests validating Excel cluster capacity structure (no legacy namespace totals rows/comments)."""
import pytest
import tempfile
import os
from datetime import datetime, timezone
from data_gatherer.reporting.cluster_capacity_report import ClusterCapacityReport
from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.util.hash import sha256_of_manifest


def test_excel_sections_and_totals(sample_db):
    """Ensure Excel has summary, namespace capacity table with Totals, and detail sections."""
    report = ClusterCapacityReport()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "cluster_capacity.xlsx")
        report.generate(sample_db, "test-cluster", out_path, format='excel')
        assert os.path.exists(out_path)
        try:
            from openpyxl import load_workbook
        except ImportError:
            pytest.skip("openpyxl not available")
        wb = load_workbook(out_path)
        ws = wb.active
        scope_row = None
        ns_header_row = None
        totals_row = None
        detail_header_found = False
        for r in range(1, ws.max_row+1):
            v1 = ws.cell(row=r, column=1).value
            if v1 == 'Scope':
                scope_row = r
            elif v1 == 'Namespace':
                ns_header_row = r
            elif v1 == 'Totals' and ns_header_row and r > ns_header_row and totals_row is None:
                totals_row = r
            elif v1 == 'Kind' and ws.cell(row=r, column=2).value == 'Workload Name':
                detail_header_found = True
        assert scope_row, 'Summary scope section missing'
        assert ns_header_row, 'Namespace capacity header missing'
        assert totals_row, 'Totals row missing in namespace capacity table'
        assert detail_header_found, 'Per-namespace detail section missing'


def test_excel_namespaces_present_in_html(sample_db):
    """Namespaces listed in Excel capacity table should appear in HTML report."""
    report = ClusterCapacityReport()
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, 'report.html')
        xlsx_path = os.path.join(tmpdir, 'report.xlsx')
        report.generate(sample_db, 'test-cluster', html_path, format='html')
        report.generate(sample_db, 'test-cluster', xlsx_path, format='excel')
        with open(html_path, 'r') as f:
            html = f.read()
        try:
            from openpyxl import load_workbook
        except ImportError:
            pytest.skip('openpyxl not available')
        wb = load_workbook(xlsx_path)
        ws = wb.active
        ns_header_row = None
        for r in range(1, ws.max_row+1):
            if ws.cell(row=r, column=1).value == 'Namespace':
                ns_header_row = r
                break
        assert ns_header_row
        namespaces = []
        for r in range(ns_header_row+1, ns_header_row+100):
            name = ws.cell(row=r, column=1).value
            if not name:
                break
            if name == 'Totals':
                continue
            namespaces.append(name)
        assert namespaces
        for ns in namespaces:
            assert ns in html, f'Namespace {ns} missing from HTML content'


def test_excel_namespace_order_matches_detail_sections(sample_db):
    """Order of namespaces in capacity table should match first appearance in detail sections."""
    report = ClusterCapacityReport()
    with tempfile.TemporaryDirectory() as tmpdir:
        xlsx_path = os.path.join(tmpdir, 'report.xlsx')
        report.generate(sample_db, 'test-cluster', xlsx_path, format='excel')
        try:
            from openpyxl import load_workbook
        except ImportError:
            pytest.skip('openpyxl not available')
        wb = load_workbook(xlsx_path)
        ws = wb.active
        # Capacity table namespaces
        ns_header_row = None
        for r in range(1, ws.max_row+1):
            if ws.cell(row=r, column=1).value == 'Namespace':
                ns_header_row = r
                break
        assert ns_header_row
        cap_names = []
        for r in range(ns_header_row+1, ns_header_row+100):
            name = ws.cell(row=r, column=1).value
            if not name:
                break
            if name == 'Totals':
                continue
            cap_names.append(name)
        # Detail sections: scan for Kind header rows and look upward for namespace name label row inserted previously (the implementation writes a blank separator then title row with namespace name before detail table)
        detail_first_seen = []
        for r in range(1, ws.max_row+1):
            if ws.cell(row=r, column=1).value == 'Kind' and ws.cell(row=r, column=2).value == 'Workload Name':
                # Search backwards up to 5 rows for namespace name (non-empty, not 'Totals', not 'Namespace')
                for back in range(r-1, max(0, r-6), -1):
                    candidate = ws.cell(row=back, column=1).value
                    if candidate and candidate not in ('Totals', 'Namespace', 'Scope') and candidate not in detail_first_seen and candidate != 'Kind':
                        detail_first_seen.append(candidate)
                        break
        # We only assert relative ordering for namespaces that appear in both lists
        overlap = [n for n in cap_names if n in detail_first_seen]
        detail_overlap = [n for n in detail_first_seen if n in overlap]
        assert overlap == detail_overlap, 'Namespace order mismatch between capacity and detail sections'


@pytest.fixture
def sample_db(tmp_path):
    """Create a sample database with test data."""
    db_path = tmp_path / 'test.db'
    db = WorkloadDB(str(db_path))
    now = datetime.now(timezone.utc)
    
    # Insert test workloads across multiple namespaces
    manifests = [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "app1", "namespace": "ns1"},
            "spec": {
                "replicas": 2,
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "main",
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                                "limits": {"cpu": "200m", "memory": "256Mi"}
                            }
                        }]
                    }
                }
            }
        },
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "app2", "namespace": "ns1"},
            "spec": {
                "replicas": 3,
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "main",
                            "resources": {
                                "requests": {"cpu": "200m", "memory": "256Mi"},
                                "limits": {"cpu": "400m", "memory": "512Mi"}
                            }
                        }]
                    }
                }
            }
        },
        {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": "db1", "namespace": "ns2"},
            "spec": {
                "replicas": 1,
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "postgres",
                            "resources": {
                                "requests": {"cpu": "500m", "memory": "1Gi"},
                                "limits": {"cpu": "1000m", "memory": "2Gi"}
                            }
                        }]
                    }
                }
            }
        }
    ]
    
    for i, manifest in enumerate(manifests):
        db.upsert_workload(
            cluster="test-cluster",
            api_version=manifest["apiVersion"],
            kind=manifest["kind"],
            namespace=manifest["metadata"]["namespace"],
            name=manifest["metadata"]["name"],
            resource_version="1",
            uid=f"u{i+1}",
            manifest=manifest,
            manifest_hash=sha256_of_manifest(manifest),
            now=now
        )
    
    # Insert node capacity data
    db.upsert_node_capacity(
        cluster="test-cluster",
        node_name="worker-1",
        node_data={
            'metadata': {
                'name': 'worker-1',
                'labels': {'node-role.kubernetes.io/worker': ''}
            },
            'status': {
                'capacity': {'cpu': '4000m', 'memory': '8Gi'},
                'allocatable': {'cpu': '3600m', 'memory': '7Gi'},
                'nodeInfo': {
                    'osImage': 'Red Hat Enterprise Linux CoreOS',
                    'kernelVersion': '5.14.0',
                    'containerRuntimeVersion': 'cri-o://1.24.1'
                }
            }
        },
        now=now
    )
    
    return db
