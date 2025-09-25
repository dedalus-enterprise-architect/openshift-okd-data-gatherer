from datetime import datetime, timezone, timedelta
from data_gatherer.persistence.db import WorkloadDB
import os
import tempfile


def test_hard_delete_and_insert_snapshot_mode():
    """In snapshot mode a missing workload is hard-deleted and reappears as a fresh insert."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, 'data.db')
        db = WorkloadDB(db_path)
        now = datetime.now(timezone.utc)

        # Initial insert
        status, _ = db.upsert_workload(
            cluster='c1', api_version='apps/v1', kind='Deployment', namespace='ns', name='app',
            resource_version='1', uid='u1', manifest={'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'app', 'namespace': 'ns'}},
            manifest_hash='hashA', now=now
        )
        assert status == 'inserted'

        # Hard delete via empty alive set
        removed = db.mark_deleted('c1', alive_keys=[])
        assert removed == 1

        later = now + timedelta(minutes=5)
        # Reinsertion with same hash is treated as a new insert
        status2, _ = db.upsert_workload(
            cluster='c1', api_version='apps/v1', kind='Deployment', namespace='ns', name='app',
            resource_version='2', uid='u1', manifest={'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'app', 'namespace': 'ns'}},
            manifest_hash='hashA', now=later
        )
        assert status2 == 'inserted'

        # Change hash -> update
        status3, _ = db.upsert_workload(
            cluster='c1', api_version='apps/v1', kind='Deployment', namespace='ns', name='app',
            resource_version='3', uid='u1', manifest={'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'app', 'namespace': 'ns', 'labels': {'v': '2'}}},
            manifest_hash='hashB', now=later + timedelta(minutes=1)
        )
        assert status3 == 'updated'
