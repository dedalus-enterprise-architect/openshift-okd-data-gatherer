from click.testing import CliRunner
from data_gatherer.run import cli


def test_nodes_report_generation(tmp_path):
    """Test nodes report generation with sample node data."""
    from data_gatherer.persistence.db import WorkloadDB
    from datetime import datetime, timezone

    # Create test database with node data
    db_path = tmp_path / 'data.db'
    db = WorkloadDB(str(db_path))
    datetime.now(timezone.utc)  # Maintain previous now usage (ignored)

    # Insert sample nodes with different roles
    nodes_data = [
        ('master-1', 'master', 'm5.xlarge', 'us-west-2a', '4000m', '16Gi', '3800m', '15Gi'),
        ('master-2', 'master', 'm5.xlarge', 'us-west-2b', '4000m', '16Gi', '3800m', '15Gi'),
        ('worker-1', 'worker', 'm5.2xlarge', 'us-west-2a', '8000m', '32Gi', '7600m', '30Gi'),
        ('worker-2', 'worker', 'm5.2xlarge', 'us-west-2b', '8000m', '32Gi', '7600m', '30Gi'),
        ('infra-1', 'infra', 'm5.large', 'us-west-2c', '2000m', '8Gi', '1900m', '7Gi'),
    ]

    for node_name, role, instance_type, zone, cpu_cap, mem_cap, cpu_alloc, mem_alloc in nodes_data:
        db.upsert_node_capacity('test-cluster', node_name, {
            'metadata': {
                'name': node_name,
                'labels': {f'node-role.kubernetes.io/{role}': ''},
            },
            'status': {
                'capacity': {'cpu': cpu_cap, 'memory': mem_cap},
                'allocatable': {'cpu': cpu_alloc, 'memory': mem_alloc},
                'nodeInfo': {
                    'osImage': 'Red Hat Enterprise Linux CoreOS',
                    'kernelVersion': '5.14.0',
                    'containerRuntimeVersion': 'cri-o://1.24.1'
                }
            }
        })

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
    include_kinds: [Node]
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

    # Generate nodes report
    runner = CliRunner()
    result = runner.invoke(cli, ['--config', str(cfg_path), 'report', '--cluster', 'test-cluster', '--type', 'nodes'])
    assert result.exit_code == 0, result.output

    # Verify report was generated
    reports_dir = cluster_dir / 'reports'
    files = list(reports_dir.glob('nodes-*.html'))
    assert files, 'No nodes report produced'

    # Verify report content
    content = files[0].read_text()
    assert 'Nodes resource report: test-cluster' in content
    assert 'Resource Summary by Node Role' in content
    assert '<td><strong>master</strong></td>' in content
    assert '<td><strong>worker</strong></td>' in content
    assert '<td><strong>infra</strong></td>' in content
    assert 'Cluster Totals' in content
    assert 'Total Nodes:</strong> 5' in content

    # Check for specific resource calculations
    assert '7.6' in content  # Total master allocatable CPU (2 * 3.8)
    assert '15.2' in content  # Total worker allocatable CPU (2 * 7.6)


def test_nodes_report_empty_data(tmp_path):
    """Test nodes report generation when no node data exists."""
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
    include_kinds: [Node]
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
    result = runner.invoke(cli, ['--config', str(cfg_path), 'report', '--cluster', 'empty-cluster', '--type', 'nodes'])
    assert result.exit_code == 0, result.output

    reports_dir = cluster_dir / 'reports'
    files = list(reports_dir.glob('nodes-*.html'))
    assert files, 'No nodes report produced'

    content = files[0].read_text()
    assert 'No node data available for this cluster' in content
