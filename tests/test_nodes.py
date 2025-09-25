from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.sync.engine import SyncEngine
import tempfile
import os
from datetime import datetime


def test_node_capacity_storage():
    """Test that node capacity data is properly stored"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = WorkloadDB(db_path)
        
        # Sample node data
        node_data = {
            'metadata': {
                'name': 'worker-1',
                'labels': {
                    'node-role.kubernetes.io/worker': '',
                    'node.kubernetes.io/instance-type': 'm5.large',
                    'topology.kubernetes.io/zone': 'us-west-2a'
                }
            },
            'status': {
                'capacity': {
                    'cpu': '2000m',
                    'memory': '8Gi',
                    'ephemeral-storage': '100Gi',
                    'pods': '110'
                },
                'allocatable': {
                    'cpu': '1900m', 
                    'memory': '7Gi',
                    'ephemeral-storage': '90Gi',
                    'pods': '110'
                },
                'nodeInfo': {
                    'osImage': 'Amazon Linux 2',
                    'kernelVersion': '5.4.0',
                    'containerRuntimeVersion': 'containerd://1.4.6'
                }
            }
        }
        
        # Test node capacity upsert
        status, changed = db.upsert_node_capacity('test-cluster', 'worker-1', node_data)
        assert status == 'inserted'
        assert changed == True
        
        # Test summary includes node data
        summary = db.summary('test-cluster')
        assert 'nodes' in summary
        assert summary['nodes']['total_nodes'] == 1
        assert summary['nodes']['by_role']['worker'] == 1


def test_cluster_scoped_sync():
    """Test syncing cluster-scoped resources like nodes"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = WorkloadDB(db_path)
        engine = SyncEngine(db, 'test-cluster')
        
        # Sample node items
        node_items = [{
            'apiVersion': 'v1',
            'kind': 'Node',
            'metadata': {
                'name': 'master-1',
                'labels': {
                    'node-role.kubernetes.io/control-plane': '',
                }
            },
            'status': {
                'capacity': {'cpu': '4000m', 'memory': '16Gi'},
                'allocatable': {'cpu': '3800m', 'memory': '15Gi'}
            }
        }]
        
        # Sync nodes
        alive = engine.sync_kind('v1', 'Node', node_items)
        
        # Verify both workload table and node_capacity table are populated
        summary = db.summary('test-cluster')
        assert summary['by_kind']['Node'] == 1
        assert summary['nodes']['total_nodes'] == 1
        assert summary['nodes']['by_role']['master'] == 1


def test_node_role_detection():
    """Test node role detection from labels"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = WorkloadDB(db_path)
        
        # Test master node
        master_node = {
            'metadata': {
                'name': 'master-1',
                'labels': {'node-role.kubernetes.io/control-plane': ''}
            },
            'status': {'capacity': {}, 'allocatable': {}, 'nodeInfo': {}}
        }
        
        db.upsert_node_capacity('test', 'master-1', master_node)
        
        # Test infra node  
        infra_node = {
            'metadata': {
                'name': 'infra-1',
                'labels': {'node-role.kubernetes.io/infra': ''}
            },
            'status': {'capacity': {}, 'allocatable': {}, 'nodeInfo': {}}
        }
        
        db.upsert_node_capacity('test', 'infra-1', infra_node)
        
        summary = db.summary('test')
        assert summary['nodes']['by_role']['master'] == 1
        assert summary['nodes']['by_role']['infra'] == 1
