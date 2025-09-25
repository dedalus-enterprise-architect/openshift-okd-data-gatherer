from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.persistence.queries import NodeQueries
from data_gatherer.persistence.workload_queries import WorkloadQueries
from datetime import datetime, timezone
import json


def _make_db(tmp_path):
    return WorkloadDB(str(tmp_path / 'data.db'))


def test_node_queries_roundtrip(tmp_path):
    db = _make_db(tmp_path)
    # Insert a node via workload + node capacity APIs
    node_manifest = {'metadata': {'name': 'node-a'}, 'status': {'capacity': {}, 'allocatable': {}, 'nodeInfo': {}}}
    db.upsert_node_capacity('c1', 'node-a', node_manifest)
    nq = NodeQueries(db)
    nodes = nq.list_active_nodes('c1')
    assert len(nodes) == 1
    assert nodes[0].node_name == 'node-a'


def test_workload_queries(tmp_path):
    db = _make_db(tmp_path)
    now = datetime.now(timezone.utc)
    manifest = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'cm1'}}
    db.upsert_workload('c1', 'v1', 'ConfigMap', 'default', 'cm1', '1', 'uid1', manifest, 'hash123', now)
    wq = WorkloadQueries(db)
    by_kind = wq.count_by_kind('c1')
    assert by_kind.get('ConfigMap') == 1
    rows = wq.list_by_kind('c1', 'ConfigMap')
    assert len(rows) == 1
    assert rows[0]['name'] == 'cm1'
    assert rows[0]['manifest']['metadata']['name'] == 'cm1'
