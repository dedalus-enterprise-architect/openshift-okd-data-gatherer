"""
Non-regression tests for totals calculation logic across all capacity reports.

These tests verify that:
1. Container-level totals = resource × replicas
2. Namespace totals = sum of all workloads in namespace (main containers only)
3. Cluster-wide totals = sum of all namespace totals
4. DaemonSet replicas = worker node count (when eligible)
5. Init container overhead = all containers total - main containers total
6. Worker node filtering is applied correctly
"""
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timezone

from data_gatherer.reporting.cluster_capacity_report import ClusterCapacityReport
from data_gatherer.reporting.cluster_capacity_report import ClusterCapacityReport
from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.util.hash import sha256_of_manifest


@pytest.fixture
def comprehensive_test_db(tmp_path):
    """
    Create a test database with comprehensive scenarios for totals calculation:
    - Multiple namespaces
    - Multiple workload types (Deployment, StatefulSet, DaemonSet)
    - Main and init containers
    - Worker nodes with known capacity
    """
    db_path = tmp_path / 'test.db'
    db = WorkloadDB(str(db_path))
    now = datetime.now(timezone.utc)
    
    # Create worker nodes
    worker_nodes = [
        {
            'metadata': {'name': 'worker-1', 'labels': {'node-role.kubernetes.io/worker': ''}},
            'status': {
                'capacity': {'cpu': '4', 'memory': '16Gi'},
                'allocatable': {'cpu': '3800m', 'memory': '15Gi'}
            }
        },
        {
            'metadata': {'name': 'worker-2', 'labels': {'node-role.kubernetes.io/worker': ''}},
            'status': {
                'capacity': {'cpu': '4', 'memory': '16Gi'},
                'allocatable': {'cpu': '3800m', 'memory': '15Gi'}
            }
        },
        {
            'metadata': {'name': 'worker-3', 'labels': {'node-role.kubernetes.io/worker': ''}},
            'status': {
                'capacity': {'cpu': '4', 'memory': '16Gi'},
                'allocatable': {'cpu': '3800m', 'memory': '15Gi'}
            }
        }
    ]
    
    # Add master node (should be excluded from worker calculations)
    master_node = {
        'metadata': {'name': 'master-1', 'labels': {'node-role.kubernetes.io/master': ''}},
        'status': {
            'capacity': {'cpu': '8', 'memory': '32Gi'},
            'allocatable': {'cpu': '7800m', 'memory': '30Gi'}
        }
    }
    
    for node in worker_nodes + [master_node]:
        db.upsert_node_capacity(
            cluster='test-cluster',
            node_name=node['metadata']['name'],
            node_data=node,
            now=now
        )
    
    # Scenario 1: Deployment with main + init containers in namespace "app"
    deployment_manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {'name': 'web-app', 'namespace': 'app'},
        'spec': {
            'replicas': 3,
            'template': {
                'spec': {
                    'initContainers': [
                        {
                            'name': 'init-db',
                            'resources': {
                                'requests': {'cpu': '100m', 'memory': '128Mi'},
                                'limits': {'cpu': '200m', 'memory': '256Mi'}
                            }
                        }
                    ],
                    'containers': [
                        {
                            'name': 'web',
                            'resources': {
                                'requests': {'cpu': '500m', 'memory': '512Mi'},
                                'limits': {'cpu': '1000m', 'memory': '1024Mi'}
                            }
                        },
                        {
                            'name': 'sidecar',
                            'resources': {
                                'requests': {'cpu': '100m', 'memory': '128Mi'},
                                'limits': {'cpu': '200m', 'memory': '256Mi'}
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Scenario 2: StatefulSet in namespace "database"
    statefulset_manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'StatefulSet',
        'metadata': {'name': 'postgres', 'namespace': 'database'},
        'spec': {
            'replicas': 2,
            'template': {
                'spec': {
                    'containers': [
                        {
                            'name': 'db',
                            'resources': {
                                'requests': {'cpu': '1000m', 'memory': '2048Mi'},
                                'limits': {'cpu': '2000m', 'memory': '4096Mi'}
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Scenario 3: DaemonSet that runs on worker nodes (namespace "monitoring")
    # Should have replicas = 3 (number of worker nodes)
    daemonset_manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'DaemonSet',
        'metadata': {'name': 'node-exporter', 'namespace': 'monitoring'},
        'spec': {
            'template': {
                'spec': {
                    'containers': [
                        {
                            'name': 'exporter',
                            'resources': {
                                'requests': {'cpu': '50m', 'memory': '64Mi'},
                                'limits': {'cpu': '100m', 'memory': '128Mi'}
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Scenario 4: DaemonSet that targets master nodes (should be excluded from worker calculations)
    master_daemonset_manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'DaemonSet',
        'metadata': {'name': 'master-monitor', 'namespace': 'kube-system'},
        'spec': {
            'template': {
                'spec': {
                    'nodeSelector': {
                        'node-role.kubernetes.io/master': ''
                    },
                    'containers': [
                        {
                            'name': 'monitor',
                            'resources': {
                                'requests': {'cpu': '100m', 'memory': '128Mi'},
                                'limits': {'cpu': '200m', 'memory': '256Mi'}
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Insert workloads
    db.upsert_workload(
        cluster='test-cluster', api_version='apps/v1', kind='Deployment',
        namespace='app', name='web-app', resource_version='1', uid='u1',
        manifest=deployment_manifest, manifest_hash=sha256_of_manifest(deployment_manifest), now=now
    )
    
    db.upsert_workload(
        cluster='test-cluster', api_version='apps/v1', kind='StatefulSet',
        namespace='database', name='postgres', resource_version='1', uid='u2',
        manifest=statefulset_manifest, manifest_hash=sha256_of_manifest(statefulset_manifest), now=now
    )
    
    db.upsert_workload(
        cluster='test-cluster', api_version='apps/v1', kind='DaemonSet',
        namespace='monitoring', name='node-exporter', resource_version='1', uid='u3',
        manifest=daemonset_manifest, manifest_hash=sha256_of_manifest(daemonset_manifest), now=now
    )
    
    db.upsert_workload(
        cluster='test-cluster', api_version='apps/v1', kind='DaemonSet',
        namespace='kube-system', name='master-monitor', resource_version='1', uid='u4',
        manifest=master_daemonset_manifest, manifest_hash=sha256_of_manifest(master_daemonset_manifest), now=now
    )
    
    return db, str(db_path)


class TestContainerLevelTotals:
    """Test that container-level totals = resource × replicas."""
    
    def test_deployment_container_totals(self, comprehensive_test_db):
        """Verify Deployment container totals calculation."""
        db, _ = comprehensive_test_db
        report = ContainerCapacityReport()
        
        table_data = report._generate_capacity_data(db, 'test-cluster')
        rows = table_data['table_rows']
        
        # Find the web-app Deployment main container row
        web_row = next((r for r in rows if r[2] == 'web-app' and r[3] == 'web'), None)
        assert web_row is not None, "web-app main container not found"
        
        # Verify: replicas = 3, CPU request = 500m, total = 1500m
        assert web_row[5] == 3  # Replicas
        assert web_row[6] == 500  # CPU_req_m
        assert web_row[10] == 1500  # CPU_req_m_total (500 × 3)
        assert web_row[8] == 512  # Mem_req_Mi
        assert web_row[12] == 1536  # Mem_req_Mi_total (512 × 3)
    
    def test_daemonset_container_totals(self, comprehensive_test_db):
        """Verify DaemonSet container totals = resource × worker_node_count."""
        db, _ = comprehensive_test_db
        report = ContainerCapacityReport()
        
        table_data = report._generate_capacity_data(db, 'test-cluster')
        rows = table_data['table_rows']
        
        # Find the node-exporter DaemonSet row
        ds_row = next((r for r in rows if r[2] == 'node-exporter'), None)
        assert ds_row is not None, "node-exporter DaemonSet not found"
        
        # Verify: replicas = 3 (worker nodes), CPU request = 50m, total = 150m
        assert ds_row[5] == 3  # Replicas (number of worker nodes)
        assert ds_row[6] == 50  # CPU_req_m
        assert ds_row[10] == 150  # CPU_req_m_total (50 × 3)
        assert ds_row[8] == 64  # Mem_req_Mi
        assert ds_row[12] == 192  # Mem_req_Mi_total (64 × 3)
    
    def test_statefulset_container_totals(self, comprehensive_test_db):
        """Verify StatefulSet container totals calculation."""
        db, _ = comprehensive_test_db
        report = ContainerCapacityReport()
        
        table_data = report._generate_capacity_data(db, 'test-cluster')
        rows = table_data['table_rows']
        
        # Find the postgres StatefulSet row
        ss_row = next((r for r in rows if r[2] == 'postgres'), None)
        assert ss_row is not None, "postgres StatefulSet not found"
        
        # Verify: replicas = 2, CPU request = 1000m, total = 2000m
        assert ss_row[5] == 2  # Replicas
        assert ss_row[6] == 1000  # CPU_req_m
        assert ss_row[10] == 2000  # CPU_req_m_total (1000 × 2)
        assert ss_row[8] == 2048  # Mem_req_Mi
        assert ss_row[12] == 4096  # Mem_req_Mi_total (2048 × 2)


class TestClusterWideTotals:
    """Test cluster-wide aggregation totals."""
    
    def test_main_containers_only_aggregation(self, comprehensive_test_db):
        """Verify that main container totals exclude init containers."""
        db, _ = comprehensive_test_db
        report = ContainerCapacityReport()
        
        table_data = report._generate_capacity_data(db, 'test-cluster')
        aggregates = table_data['aggregates']
        
        # Expected main container totals:
        # - web-app: (500m + 100m) × 3 = 1800m CPU, (512 + 128) × 3 = 1920Mi Memory
        # - postgres: 1000m × 2 = 2000m CPU, 2048 × 2 = 4096Mi Memory
        # - node-exporter: 50m × 3 = 150m CPU, 64 × 3 = 192Mi Memory
        # Total: 1800 + 2000 + 150 = 3950m CPU, 1920 + 4096 + 192 = 6208Mi Memory
        
        assert aggregates['main_cpu_total'] == 3950, \
            f"Expected main_cpu_total=3950, got {aggregates['main_cpu_total']}"
        assert aggregates['main_mem_total'] == 6208, \
            f"Expected main_mem_total=6208, got {aggregates['main_mem_total']}"
    
    # Removed tests for all_* and overhead calculations (init containers discarded globally)
    
    def test_limits_totals(self, comprehensive_test_db):
        """Verify that limits are aggregated correctly."""
        db, _ = comprehensive_test_db
        report = ContainerCapacityReport()
        
        table_data = report._generate_capacity_data(db, 'test-cluster')
        aggregates = table_data['aggregates']
        
        # Expected main container limits:
        # - web-app: (1000m + 200m) × 3 = 3600m CPU, (1024 + 256) × 3 = 3840Mi Memory
        # - postgres: 2000m × 2 = 4000m CPU, 4096 × 2 = 8192Mi Memory
        # - node-exporter: 100m × 3 = 300m CPU, 128 × 3 = 384Mi Memory
        # Total: 3600 + 4000 + 300 = 7900m CPU, 3840 + 8192 + 384 = 12416Mi Memory
        
        assert aggregates['main_cpu_lim_total'] == 7900, \
            f"Expected main_cpu_lim_total=7900, got {aggregates['main_cpu_lim_total']}"
        assert aggregates['main_mem_lim_total'] == 12416, \
            f"Expected main_mem_lim_total=12416, got {aggregates['main_mem_lim_total']}"


class TestNamespaceTotals:
    """Test namespace-level totals aggregation."""
    
    def test_cluster_capacity_namespace_totals(self, comprehensive_test_db):
        """Verify cluster capacity report namespace totals."""
        db, _ = comprehensive_test_db
        report = ClusterCapacityReport()
        
        capacity_data = report._generate_capacity_data(db, 'test-cluster')
        ns_totals = capacity_data['ns_totals']
        
        # Expected namespace totals (main + init containers):
        # - app: (500+100+100) × 3 + 100 × 3 = 1800 + 300 = 2100m CPU, 1920 + 384 = 2304Mi Memory
        # - database: 1000 × 2 = 2000m CPU, 2048 × 2 = 4096Mi Memory
        # - monitoring: 50 × 3 = 150m CPU, 64 × 3 = 192Mi Memory
        # (kube-system master-monitor should be excluded from worker calculations)
        
        assert 'app' in ns_totals
        assert ns_totals['app']['cpu'] == 2100, \
            f"Expected app namespace CPU=2100m, got {ns_totals['app']['cpu']}"
        assert ns_totals['app']['mem'] == 2304, \
            f"Expected app namespace Memory=2304Mi, got {ns_totals['app']['mem']}"
        
        assert 'database' in ns_totals
        assert ns_totals['database']['cpu'] == 2000, \
            f"Expected database namespace CPU=2000m, got {ns_totals['database']['cpu']}"
        assert ns_totals['database']['mem'] == 4096, \
            f"Expected database namespace Memory=4096Mi, got {ns_totals['database']['mem']}"
        
        assert 'monitoring' in ns_totals
        assert ns_totals['monitoring']['cpu'] == 150, \
            f"Expected monitoring namespace CPU=150m, got {ns_totals['monitoring']['cpu']}"
        assert ns_totals['monitoring']['mem'] == 192, \
            f"Expected monitoring namespace Memory=192Mi, got {ns_totals['monitoring']['mem']}"
    
    def test_cluster_wide_sum_matches_namespace_sum(self, comprehensive_test_db):
        """Verify that cluster-wide totals equal sum of namespace totals."""
        db, _ = comprehensive_test_db
        report = ClusterCapacityReport()
        
        capacity_data = report._generate_capacity_data(db, 'test-cluster')
        ns_totals = capacity_data['ns_totals']
        
        # Sum all namespace CPU requests
        total_cpu = sum(ns['cpu'] for ns in ns_totals.values())
        total_mem = sum(ns['mem'] for ns in ns_totals.values())
        
        # Should equal: 2100 + 2000 + 150 = 4250m CPU, 2304 + 4096 + 192 = 6592Mi Memory
        assert total_cpu == 4250, f"Expected total CPU=4250m, got {total_cpu}"
        assert total_mem == 6592, f"Expected total Memory=6592Mi, got {total_mem}"


class TestWorkerNodeFiltering:
    """Test that worker node filtering is applied correctly."""
    
    def test_master_daemonset_excluded_from_worker_calculations(self, comprehensive_test_db):
        """Verify that DaemonSets targeting master nodes have zero replicas for worker calculations."""
        db, _ = comprehensive_test_db
        report = ContainerCapacityReport()
        
        table_data = report._generate_capacity_data(db, 'test-cluster')
        rows = table_data['table_rows']
        
        # master-monitor DaemonSet should appear in results but with replicas=0
        # (it targets master nodes, not worker nodes)
        master_ds_row = next((r for r in rows if r[2] == 'master-monitor'), None)
        assert master_ds_row is not None, \
            "master-monitor DaemonSet should appear in results"
        
        # Replicas should be 0 since it doesn't run on worker nodes
        assert master_ds_row[5] == 0, \
            f"master-monitor should have 0 replicas (worker-only count), got {master_ds_row[5]}"
        
        # Totals should also be 0
        assert master_ds_row[10] == 0, "CPU total should be 0"
        assert master_ds_row[12] == 0, "Memory total should be 0"
    
    def test_worker_node_count_calculation(self, comprehensive_test_db):
        """Verify correct worker node count."""
        db, _ = comprehensive_test_db
        report = ContainerCapacityReport()
        
        table_data = report._generate_capacity_data(db, 'test-cluster')
        node_capacity = table_data['node_capacity']
        
        # Should have 3 worker nodes (master-1 excluded)
        assert node_capacity.get('worker_node_count', 0) == 3, \
            f"Expected 3 worker nodes, got {node_capacity.get('worker_node_count', 0)}"
    
    def test_worker_node_allocatable_capacity(self, comprehensive_test_db):
        """Verify worker node allocatable capacity aggregation."""
        db, _ = comprehensive_test_db
        report = ClusterCapacityReport()
        
        capacity_data = report._generate_capacity_data(db, 'test-cluster')
        node_capacity = capacity_data['node_capacity']
        
        # Expected: 3 workers × 3800m CPU = 11400m, 3 workers × 15360Mi Memory = 46080Mi
        assert node_capacity['total_cpu_alloc'] == 11400, \
            f"Expected total_cpu_alloc=11400m, got {node_capacity['total_cpu_alloc']}"
        assert node_capacity['total_mem_alloc'] == 46080, \
            f"Expected total_mem_alloc=46080Mi, got {node_capacity['total_mem_alloc']}"


class TestEdgeCases:
    """Test edge cases in totals calculation."""
    
    def test_missing_resources_dont_break_totals(self, tmp_path):
        """Verify that containers with missing resources don't break aggregation."""
        db_path = tmp_path / 'edge.db'
        db = WorkloadDB(str(db_path))
        now = datetime.now(timezone.utc)
        
        # Workload with missing resource specs
        manifest = {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {'name': 'no-resources', 'namespace': 'test'},
            'spec': {
                'replicas': 2,
                'template': {
                    'spec': {
                        'containers': [
                            {
                                'name': 'app',
                                'image': 'nginx'
                                # No resources block
                            }
                        ]
                    }
                }
            }
        }
        
        db.upsert_workload(
            cluster='test', api_version='apps/v1', kind='Deployment',
            namespace='test', name='no-resources', resource_version='1', uid='u1',
            manifest=manifest, manifest_hash=sha256_of_manifest(manifest), now=now
        )
        
        report = ContainerCapacityReport()
        table_data = report._generate_capacity_data(db, 'test')
        aggregates = table_data['aggregates']
        
        # Aggregates should be zero (no resources specified)
        assert aggregates['main_cpu_total'] == 0
        assert aggregates['main_mem_total'] == 0
    
    def test_zero_replicas_handled_correctly(self, tmp_path):
        """Verify that workloads with zero replicas are handled correctly."""
        db_path = tmp_path / 'zero.db'
        db = WorkloadDB(str(db_path))
        now = datetime.now(timezone.utc)
        
        # Deployment scaled to zero
        manifest = {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {'name': 'scaled-down', 'namespace': 'test'},
            'spec': {
                'replicas': 0,
                'template': {
                    'spec': {
                        'containers': [
                            {
                                'name': 'app',
                                'resources': {
                                    'requests': {'cpu': '100m', 'memory': '128Mi'}
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        db.upsert_workload(
            cluster='test', api_version='apps/v1', kind='Deployment',
            namespace='test', name='scaled-down', resource_version='1', uid='u1',
            manifest=manifest, manifest_hash=sha256_of_manifest(manifest), now=now
        )
        
        report = ContainerCapacityReport()
        table_data = report._generate_capacity_data(db, 'test')
        
        # Should have row with replicas=0 and totals=0
        rows = table_data['table_rows']
        assert len(rows) == 1
        assert rows[0][5] == 0  # Replicas
        assert rows[0][10] == 0  # CPU total (100 × 0)
        assert rows[0][12] == 0  # Memory total (128 × 0)
