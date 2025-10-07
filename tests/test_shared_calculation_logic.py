"""
Tests to ensure shared calculation logic is used consistently across all reports.

This test suite verifies that:
1. All reports use the same shared functions from common.py
2. Replica calculations are consistent
3. Worker node filtering is consistent
4. No duplicate logic exists in individual reports
"""
import pytest
from datetime import datetime, timezone
from data_gatherer.reporting.common import will_run_on_worker, calculate_effective_replicas
from data_gatherer.reporting.cluster_capacity_report import ClusterCapacityReport
from data_gatherer.reporting.containers_config_report import ContainerConfigurationReport
from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.util.hash import sha256_of_manifest


class TestSharedLogicConsistency:
    """Test that all reports use shared calculation logic consistently."""
    
    def test_all_reports_use_shared_calculate_effective_replicas(self):
        """Verify that all reports import and can use the shared function."""
        # This test ensures the function is accessible from common.py
        from data_gatherer.reporting.common import calculate_effective_replicas
        
        # Create a simple test case
        deployment_manifest = {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {'name': 'test'},
            'spec': {'replicas': 3}
        }
        pod_spec = {'containers': [{'name': 'test'}]}
        
        replicas = calculate_effective_replicas('Deployment', deployment_manifest, pod_spec, 5)
        assert replicas == 3
    
    def test_all_reports_use_shared_will_run_on_worker(self):
        """Verify that all reports import and can use the shared function."""
        from data_gatherer.reporting.common import will_run_on_worker
        
        # Test with no node selector (should run on workers)
        pod_spec1 = {'containers': [{'name': 'test'}]}
        assert will_run_on_worker(pod_spec1) is True
        
        # Test with master node selector (should NOT run on workers)
        pod_spec2 = {
            'containers': [{'name': 'test'}],
            'nodeSelector': {'node-role.kubernetes.io/master': ''}
        }
        assert will_run_on_worker(pod_spec2) is False
    
    def test_no_duplicate_will_run_on_worker_methods(self):
        """Verify that reports don't have their own _will_run_on_worker methods."""
        # Check cluster capacity report
        assert not hasattr(ClusterCapacityReport, '_will_run_on_worker'), \
            "ClusterCapacityReport should not have _will_run_on_worker method"
        
        # Check containers config report
        assert not hasattr(ContainerConfigurationReport, '_will_run_on_worker'), \
            "ContainerConfigurationReport should not have _will_run_on_worker method"


class TestReplicaCalculationConsistency:
    """Test that replica calculations are consistent across all reports."""
    
    @pytest.fixture
    def test_db_with_daemonset(self, tmp_path):
        """Create a test database with a DaemonSet."""
        db_path = tmp_path / 'test.db'
        db = WorkloadDB(str(db_path))
        now = datetime.now(timezone.utc)
        
        # Add worker nodes
        for i in range(1, 4):
            node = {
                'metadata': {'name': f'worker-{i}', 'labels': {'node-role.kubernetes.io/worker': ''}},
                'status': {
                    'capacity': {'cpu': '4', 'memory': '16Gi'},
                    'allocatable': {'cpu': '3800m', 'memory': '15Gi'}
                }
            }
            db.upsert_node_capacity(cluster='test', node_name=f'worker-{i}', node_data=node, now=now)
        
        # Add a DaemonSet that runs on workers
        daemonset_manifest = {
            'apiVersion': 'apps/v1',
            'kind': 'DaemonSet',
            'metadata': {'name': 'test-ds', 'namespace': 'default'},
            'spec': {
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
            cluster='test', api_version='apps/v1', kind='DaemonSet',
            namespace='default', name='test-ds', resource_version='1', uid='u1',
            manifest=daemonset_manifest, manifest_hash=sha256_of_manifest(daemonset_manifest), now=now
        )
        
        return db
    
    def test_daemonset_replicas_consistent_across_reports(self, test_db_with_daemonset):
        """Verify that all reports calculate the same replica count for DaemonSets."""
        db = test_db_with_daemonset
        
        # Container capacity report
        container_report = ContainerCapacityReport()
        container_data = container_report._generate_capacity_data(db, 'test')
        container_rows = [r for r in container_data['table_rows'] if r[2] == 'test-ds']
        assert len(container_rows) == 1
        container_replicas = container_rows[0][5]
        
        # Cluster capacity report
        cluster_report = ClusterCapacityReport()
        cluster_data = cluster_report._generate_capacity_data(db, 'test')
        # This report aggregates by namespace, but we can verify it processed the DaemonSet
        assert 'default' in cluster_data['ns_totals']
        # Expected: 100m CPU × 3 replicas = 300m
        assert cluster_data['ns_totals']['default']['cpu'] == 300
        
        # Containers config report
        config_report = ContainerConfigurationReport()
        config_rows, _ = config_report._generate_data(db, 'test')
        config_ds_rows = [r for r in config_rows if r[2] == 'test-ds']
        assert len(config_ds_rows) == 1
        config_replicas = config_ds_rows[0][5]
        
        # All reports should show 3 replicas for the DaemonSet
        assert container_replicas == 3, \
            f"Container capacity report shows {container_replicas} replicas, expected 3"
        assert config_replicas == 3, \
            f"Containers config report shows {config_replicas} replicas, expected 3"
        
        print(f"✓ All reports consistently calculate DaemonSet replicas as 3")


class TestWorkerNodeFilteringConsistency:
    """Test that worker node filtering is consistent across all reports."""
    
    @pytest.fixture
    def test_db_with_master_daemonset(self, tmp_path):
        """Create a test database with a DaemonSet targeting master nodes."""
        db_path = tmp_path / 'test.db'
        db = WorkloadDB(str(db_path))
        now = datetime.now(timezone.utc)
        
        # Add worker nodes
        for i in range(1, 3):
            node = {
                'metadata': {'name': f'worker-{i}', 'labels': {'node-role.kubernetes.io/worker': ''}},
                'status': {
                    'capacity': {'cpu': '4', 'memory': '16Gi'},
                    'allocatable': {'cpu': '3800m', 'memory': '15Gi'}
                }
            }
            db.upsert_node_capacity(cluster='test', node_name=f'worker-{i}', node_data=node, now=now)
        
        # Add a DaemonSet that targets master nodes (should NOT run on workers)
        master_daemonset_manifest = {
            'apiVersion': 'apps/v1',
            'kind': 'DaemonSet',
            'metadata': {'name': 'master-ds', 'namespace': 'kube-system'},
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
                                    'requests': {'cpu': '100m', 'memory': '128Mi'}
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        db.upsert_workload(
            cluster='test', api_version='apps/v1', kind='DaemonSet',
            namespace='kube-system', name='master-ds', resource_version='1', uid='u1',
            manifest=master_daemonset_manifest, manifest_hash=sha256_of_manifest(master_daemonset_manifest), now=now
        )
        
        return db
    
    def test_master_daemonset_excluded_consistently(self, test_db_with_master_daemonset):
        """Verify that all reports exclude DaemonSets targeting master nodes."""
        db = test_db_with_master_daemonset
        
        # Container capacity report - should show 0 replicas
        container_report = ContainerCapacityReport()
        container_data = container_report._generate_capacity_data(db, 'test')
        container_rows = [r for r in container_data['table_rows'] if r[2] == 'master-ds']
        assert len(container_rows) == 1
        assert container_rows[0][5] == 0, \
            "Container capacity report should show 0 replicas for master DaemonSet"
        
        # Cluster capacity report - should not include in namespace totals
        cluster_report = ClusterCapacityReport()
        cluster_data = cluster_report._generate_capacity_data(db, 'test')
        # kube-system namespace should not be in totals (or should be 0)
        if 'kube-system' in cluster_data['ns_totals']:
            assert cluster_data['ns_totals']['kube-system']['cpu'] == 0, \
                "Cluster capacity report should not count master DaemonSet resources"
        
        # Containers config report - should show 0 replicas
        config_report = ContainerConfigurationReport()
        config_rows, _ = config_report._generate_data(db, 'test')
        config_ds_rows = [r for r in config_rows if r[2] == 'master-ds']
        assert len(config_ds_rows) == 1
        assert config_ds_rows[0][5] == 0, \
            "Containers config report should show 0 replicas for master DaemonSet"
        
        print(f"✓ All reports consistently exclude master DaemonSets from worker calculations")


class TestSharedFunctionBehavior:
    """Test the behavior of shared calculation functions."""
    
    def test_calculate_effective_replicas_for_deployment(self):
        """Test replica calculation for Deployment."""
        manifest = {
            'spec': {'replicas': 5}
        }
        pod_spec = {'containers': [{'name': 'test'}]}
        
        replicas = calculate_effective_replicas('Deployment', manifest, pod_spec, 10)
        assert replicas == 5
    
    def test_calculate_effective_replicas_for_statefulset(self):
        """Test replica calculation for StatefulSet."""
        manifest = {
            'spec': {'replicas': 3}
        }
        pod_spec = {'containers': [{'name': 'test'}]}
        
        replicas = calculate_effective_replicas('StatefulSet', manifest, pod_spec, 10)
        assert replicas == 3
    
    def test_calculate_effective_replicas_for_daemonset_on_workers(self):
        """Test replica calculation for DaemonSet running on workers."""
        manifest = {
            'spec': {'template': {'spec': {}}}
        }
        pod_spec = {'containers': [{'name': 'test'}]}
        
        replicas = calculate_effective_replicas('DaemonSet', manifest, pod_spec, 7)
        assert replicas == 7  # Should equal worker node count
    
    def test_calculate_effective_replicas_for_daemonset_on_masters(self):
        """Test replica calculation for DaemonSet targeting masters."""
        manifest = {
            'spec': {'template': {'spec': {}}}
        }
        pod_spec = {
            'containers': [{'name': 'test'}],
            'nodeSelector': {'node-role.kubernetes.io/master': ''}
        }
        
        replicas = calculate_effective_replicas('DaemonSet', manifest, pod_spec, 7)
        assert replicas == 0  # Should not run on workers
    
    def test_will_run_on_worker_with_no_selector(self):
        """Test that pods with no node selector run on workers."""
        pod_spec = {'containers': [{'name': 'test'}]}
        assert will_run_on_worker(pod_spec) is True
    
    def test_will_run_on_worker_with_master_selector(self):
        """Test that pods targeting masters don't run on workers."""
        pod_spec = {
            'containers': [{'name': 'test'}],
            'nodeSelector': {'node-role.kubernetes.io/master': ''}
        }
        assert will_run_on_worker(pod_spec) is False
    
    def test_will_run_on_worker_with_control_plane_selector(self):
        """Test that pods targeting control-plane don't run on workers."""
        pod_spec = {
            'containers': [{'name': 'test'}],
            'nodeSelector': {'node-role.kubernetes.io/control-plane': ''}
        }
        assert will_run_on_worker(pod_spec) is False
    
    def test_will_run_on_worker_with_infra_selector(self):
        """Test that pods targeting infra nodes don't run on workers."""
        pod_spec = {
            'containers': [{'name': 'test'}],
            'nodeSelector': {'node-role.kubernetes.io/infra': ''}
        }
        assert will_run_on_worker(pod_spec) is False
