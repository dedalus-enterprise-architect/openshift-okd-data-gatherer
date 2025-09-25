import tempfile
import os
from data_gatherer.kube.client import STATIC_KIND_MAP
from data_gatherer.persistence.db import WorkloadDB


def test_configmap_in_static_kind_map():
    """Test that ConfigMap is properly configured in STATIC_KIND_MAP."""
    assert 'ConfigMap' in STATIC_KIND_MAP
    
    api_version, plural, namespaced = STATIC_KIND_MAP['ConfigMap']
    assert api_version == 'v1'
    assert plural == 'configmaps'
    assert namespaced == True


def test_configmap_storage():
    """Test that ConfigMaps can be stored in the database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        
        # Create test ConfigMap manifest
        configmap_manifest = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': 'test-config',
                'namespace': 'test-ns'
            },
            'data': {
                'config.properties': 'key1=value1\nkey2=value2',
                'config.yaml': 'setting:\n  enabled: true'
            }
        }
        
        # Store ConfigMap in database
        db.upsert_workload(
            cluster='test-cluster',
            api_version='v1',
            kind='ConfigMap',
            namespace='test-ns',
            name='test-config',
            resource_version='123',
            uid='test-uid',
            manifest=configmap_manifest,
            manifest_hash='test-hash'
        )
        
        # Verify it was stored
        cur = db._conn.cursor()
        result = cur.execute(
            'SELECT kind, namespace, name, manifest_json FROM workload WHERE kind = ?',
            ('ConfigMap',)
        ).fetchone()
        
        assert result is not None
        kind, namespace, name, manifest_json = result
        
        assert kind == 'ConfigMap'
        assert namespace == 'test-ns'
        assert name == 'test-config'
        
        # Verify manifest data is preserved
        import json
        stored_manifest = json.loads(manifest_json)
        assert stored_manifest['data']['config.properties'] == 'key1=value1\nkey2=value2'
        assert stored_manifest['data']['config.yaml'] == 'setting:\n  enabled: true'


def test_configmap_query():
    """Test querying ConfigMaps using WorkloadQueries."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        from data_gatherer.persistence.workload_queries import WorkloadQueries

        # Store multiple ConfigMaps
        for i in range(3):
            configmap_manifest = {
                'apiVersion': 'v1',
                'kind': 'ConfigMap',
                'metadata': {
                    'name': f'config-{i}',
                    'namespace': 'test-ns'
                },
                'data': {
                    f'key-{i}': f'value-{i}'
                }
            }

            db.upsert_workload(
                cluster='test-cluster',
                api_version='v1',
                kind='ConfigMap',
                namespace='test-ns',
                name=f'config-{i}',
                resource_version=str(100 + i),
                uid=f'test-uid-{i}',
                manifest=configmap_manifest,
                manifest_hash=f'test-hash-{i}'
            )

        # Query ConfigMaps
        wq = WorkloadQueries(db)
        configmaps = wq.list_by_kind('test-cluster', 'ConfigMap')

        assert len(configmaps) == 3

        # Verify data structure
        for cm in configmaps:
            assert cm['kind'] == 'ConfigMap'
            assert cm['namespace'] == 'test-ns'
            assert cm['name'].startswith('config-')
            assert cm['apiVersion'] == 'v1'
            assert 'manifest' in cm

        # Test count by kind
        counts = wq.count_by_kind('test-cluster')
        assert counts.get('ConfigMap', 0) == 3
