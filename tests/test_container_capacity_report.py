from click.testing import CliRunner
from data_gatherer.run import cli
import tempfile
import json


def test_container_capacity_report_generation(tmp_path):
    """Test capacity aggregation report with sample workload data."""
    from data_gatherer.persistence.db import WorkloadDB
    from datetime import datetime, timezone
    
    # Create test database with workload data
    db_path = tmp_path / 'data.db'
    db = WorkloadDB(str(db_path))
    now = datetime.now(timezone.utc)
    
    # Sample Deployment with main and init containers
    deployment_manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {'name': 'web-app', 'namespace': 'production'},
        'spec': {
            'replicas': 3,
            'template': {
                'spec': {
                    'initContainers': [
                        {
                            'name': 'init-db',
                            'image': 'busybox',
                            'resources': {
                                'requests': {'cpu': '100m', 'memory': '128Mi'}
                            }
                        }
                    ],
                    'containers': [
                        {
                            'name': 'web',
                            'image': 'nginx',
                            'resources': {
                                'requests': {'cpu': '200m', 'memory': '256Mi'}
                            }
                        },
                        {
                            'name': 'sidecar',
                            'image': 'proxy',
                            'resources': {
                                'requests': {'cpu': '50m', 'memory': '64Mi'}
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Sample StatefulSet in different namespace
    statefulset_manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'StatefulSet',
        'metadata': {'name': 'database', 'namespace': 'storage'},
        'spec': {
            'replicas': 2,
            'template': {
                'spec': {
                    'containers': [
                        {
                            'name': 'db',
                            'image': 'postgres',
                            'resources': {
                                'requests': {'cpu': '500m', 'memory': '1Gi'}
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Sample Job with no init containers
    job_manifest = {
        'apiVersion': 'batch/v1',
        'kind': 'Job',
        'metadata': {'name': 'batch-process', 'namespace': 'production'},
        'spec': {
            'parallelism': 2,
            'template': {
                'spec': {
                    'containers': [
                        {
                            'name': 'processor',
                            'image': 'batch-app',
                            'resources': {
                                'requests': {'cpu': '1000m', 'memory': '512Mi'}
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
        namespace='production', name='web-app', resource_version='1', uid='u1',
        manifest=deployment_manifest, manifest_hash='h1', now=now
    )
    
    db.upsert_workload(
        cluster='test-cluster', api_version='apps/v1', kind='StatefulSet',
        namespace='storage', name='database', resource_version='1', uid='u2',
        manifest=statefulset_manifest, manifest_hash='h2', now=now
    )
    
    db.upsert_workload(
        cluster='test-cluster', api_version='batch/v1', kind='Job',
        namespace='production', name='batch-process', resource_version='1', uid='u3',
        manifest=job_manifest, manifest_hash='h3', now=now
    )
    
    db._conn.close()
    
    # Create config file
    cfg_content = f'''storage:
  base_dir: {tmp_path.as_posix()}
  write_manifest_files: false
clusters:
  - name: test-cluster
    credentials:
      host: https://dummy
      verify_ssl: false
    include_kinds: [Deployment, StatefulSet, Job]
    parallelism: 2
logging:
  level: INFO
  format: text
'''
    cfg_path = tmp_path / 'cfg.yaml'
    cfg_path.write_text(cfg_content)
    
    # Place database in expected location
    cluster_dir = tmp_path / 'test-cluster'
    cluster_dir.mkdir(exist_ok=True)
    import shutil
    shutil.copy(str(db_path), cluster_dir / 'data.db')
    
    # Generate capacity report
    runner = CliRunner()
    result = runner.invoke(cli, ['--config', str(cfg_path), 'report', '--cluster', 'test-cluster', '--type', 'capacity'])
    assert result.exit_code == 0, result.output
    
    # Verify report was generated
    reports_dir = cluster_dir / 'reports'
    files = list(reports_dir.glob('capacity-*.html'))
    assert files, 'No capacity report produced'
    
    # Verify report content
    content = files[0].read_text()
    assert 'Capacity aggregation report: test-cluster' in content
    assert 'Resource Summary by Namespace' in content
    assert '<td><strong>production</strong></td>' in content
    assert '<td><strong>storage</strong></td>' in content
    # Removed legacy Cluster Totals / Init Container Overhead summary block.
    # Validate new cluster-wide resource summary tables exist.
    assert 'Resource Summary (Cluster-wide)' in content
    assert '<h3>Containers</h3>' in content
    assert '<h3>Worker Nodes</h3>' in content
    
    # Check resource calculations
    # Production namespace: web-app (3 replicas) + batch-process (2 replicas)
    # Main containers: (200m + 50m) * 3 + 1000m * 2 = 750m + 2000m = 2750m = 2.75 cores
    assert '2.75' in content or '2750' in content
    
    # Storage namespace: database (2 replicas)
    # Main containers: 500m * 2 = 1000m = 1.00 cores
    assert '1.00' in content or '1000' in content
    
    # Init container overhead list removed; overhead still reflected in "All containers" totals.


def test_container_capacity_report_empty_data(tmp_path):
    """Test capacity report generation when no workload data exists."""
    from data_gatherer.persistence.db import WorkloadDB
    
    # Create empty database
    db_path = tmp_path / 'data.db'
    db = WorkloadDB(str(db_path))
    db._conn.close()
    
    cfg_content = f'''storage:
  base_dir: {tmp_path.as_posix()}
  write_manifest_files: false
clusters:
  - name: empty-cluster
    credentials:
      host: https://dummy
      verify_ssl: false
    include_kinds: [Deployment]
    parallelism: 2
logging:
  level: INFO
  format: text
'''
    cfg_path = tmp_path / 'cfg.yaml'
    cfg_path.write_text(cfg_content)
    
    cluster_dir = tmp_path / 'empty-cluster'
    cluster_dir.mkdir(exist_ok=True)
    import shutil
    shutil.copy(str(db_path), cluster_dir / 'data.db')
    
    runner = CliRunner()
    result = runner.invoke(cli, ['--config', str(cfg_path), 'report', '--cluster', 'empty-cluster', '--type', 'capacity'])
    assert result.exit_code == 0, result.output
    
    reports_dir = cluster_dir / 'reports'
    files = list(reports_dir.glob('capacity-*.html'))
    assert files, 'No capacity report produced'
    
    content = files[0].read_text()
    assert 'No container workloads found for this cluster' in content


def test_container_capacity_report_calculations(tmp_path):
    """Test specific resource calculation scenarios."""
    from data_gatherer.persistence.db import WorkloadDB
    from datetime import datetime, timezone
    
    db_path = tmp_path / 'data.db'
    db = WorkloadDB(str(db_path))
    now = datetime.now(timezone.utc)
    
    # Test different resource formats and replica scenarios
    deployment_manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {'name': 'test-app', 'namespace': 'test'},
        'spec': {
            'replicas': 5,  # High replica count for clear calculations
            'template': {
                'spec': {
                    'initContainers': [
                        {
                            'name': 'init',
                            'resources': {
                                'requests': {'cpu': '0.1', 'memory': '100Mi'}  # 100m CPU, 100Mi memory
                            }
                        }
                    ],
                    'containers': [
                        {
                            'name': 'main',
                            'resources': {
                                'requests': {'cpu': '200m', 'memory': '1Gi'}  # 200m CPU, 1024Mi memory
                            }
                        }
                    ]
                }
            }
        }
    }
    
    db.upsert_workload(
        cluster='calc-test', api_version='apps/v1', kind='Deployment',
        namespace='test', name='test-app', resource_version='1', uid='u1',
        manifest=deployment_manifest, manifest_hash='h1', now=now
    )
    
    db._conn.close()
    
    cfg_content = f'''storage:
  base_dir: {tmp_path.as_posix()}
  write_manifest_files: false
clusters:
  - name: calc-test
    credentials:
      host: https://dummy
      verify_ssl: false
    include_kinds: [Deployment]
    parallelism: 2
logging:
  level: INFO
  format: text
'''
    cfg_path = tmp_path / 'cfg.yaml'
    cfg_path.write_text(cfg_content)
    
    cluster_dir = tmp_path / 'calc-test'
    cluster_dir.mkdir(exist_ok=True)
    import shutil
    shutil.copy(str(db_path), cluster_dir / 'data.db')
    
    runner = CliRunner()
    result = runner.invoke(cli, ['--config', str(cfg_path), 'report', '--cluster', 'calc-test', '--type', 'capacity'])
    assert result.exit_code == 0, result.output
    
    reports_dir = cluster_dir / 'reports'
    files = list(reports_dir.glob('capacity-*.html'))
    assert files
    
    content = files[0].read_text()
    
    # Expected calculations:
    # Main containers: 200m * 5 replicas = 1000m = 1.00 CPU cores
    # Memory: 1024Mi * 5 = 5120Mi = 5.00 GiB
    # Init containers: 100m * 5 replicas = 500m = 0.50 CPU cores  
    # Memory: 100Mi * 5 = 500Mi = ~0.49 GiB
    # Total: 1.50 CPU cores, ~5.49 GiB
    
    # Validate presence of container totals row values (in tables) rather than list summary
    assert '1000' in content  # main CPU total m
    assert '5120' in content  # main memory total Mi
    assert '1500' in content  # all CPU total m (main+init)
    assert '5620' in content or '5620' in content  # total memory Mi (approx main+init)
