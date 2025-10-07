import os
from data_gatherer.run import cli
from click.testing import CliRunner
from data_gatherer.persistence.db import WorkloadDB
from datetime import datetime, timezone

def test_sizing_report(tmp_path):
    # Setup: create DB and insert node + workload data
    # Run CLI init to initialize cluster storage and DB
    runner = CliRunner()
    config_path = tmp_path / 'cfg.yaml'
    config_path.write_text(f"""storage:\n  base_dir: {tmp_path.as_posix()}\nclusters:\n  - name: test-cluster\n    credentials:\n      host: https://dummy\n      verify_ssl: false\n    include_kinds: [Deployment]\n    parallelism: 1\nlogging:\n  level: INFO\n  format: text\n""")
    result_init = runner.invoke(cli, ['--config', str(config_path), 'init', '--cluster', 'test-cluster'])
    assert result_init.exit_code == 0, result_init.output
    # Now insert node and workload data
    db_path = tmp_path / 'test-cluster' / 'data.db'
    from data_gatherer.persistence.db import WorkloadDB
    db = WorkloadDB(str(db_path))
    now = datetime.now(timezone.utc)
    db._conn.execute(
        """INSERT INTO node_capacity (cluster, node_name, first_seen, last_seen, deleted, cpu_capacity, memory_capacity, node_role)
        VALUES (?, ?, ?, ?, 0, ?, ?, ?)""",
        ('test-cluster', 'worker-1', now.isoformat(), now.isoformat(), '2000', '4096', 'worker')
    )
    manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {'name': 'demo', 'namespace': 'ns1'},
        'spec': {
            'replicas': 2,
            'template': {
                'spec': {
                    'containers': [
                        {'name': 'c1', 'resources': {'requests': {'cpu': '500m', 'memory': '1024Mi'}}},
                        {'name': 'c2', 'resources': {'requests': {'cpu': '250m', 'memory': '512Mi'}}}
                    ]
                }
            }
        }
    }
    db.upsert_workload(
        cluster='test-cluster', api_version='apps/v1', kind='Deployment',
        namespace='ns1', name='demo', resource_version='1', uid='u1',
        manifest=manifest, manifest_hash='h1', now=now
    )
    db._conn.close()
    # Prepare config
    config_path = tmp_path / 'cfg.yaml'
    config_path.write_text(f"""storage:\n  base_dir: {tmp_path.as_posix()}\nclusters:\n  - name: test-cluster\n    credentials:\n      host: https://dummy\n      verify_ssl: false\n    include_kinds: [Deployment]\n    parallelism: 1\nlogging:\n  level: INFO\n  format: text\n""")
    # Run CLI init to initialize cluster storage
    runner = CliRunner()
    result_init = runner.invoke(cli, ['--config', str(config_path), 'init', '--cluster', 'test-cluster'])
    assert result_init.exit_code == 0, result_init.output
    # Run CLI report
    result = runner.invoke(cli, ['--config', str(config_path), 'report', '--cluster', 'test-cluster', '--type', 'cluster-capacity'])
    assert result.exit_code == 0, result.output
    # Check output file exists and contains expected table
    reports_dir = tmp_path / 'test-cluster' / 'reports'
    cc_files = list(reports_dir.glob('cluster-capacity-*.html'))
    assert cc_files, 'No cluster capacity report generated'
    content = cc_files[0].read_text()
    assert 'Cluster Capacity Report' in content
    # Updated structure checks
    assert 'Namespace capacity vs Cluster capacity' in content
    assert 'Container Requests vs Allocatable resources on Worker Nodes' in content
    assert 'Free resources (Allocatable - Requests)' in content
    assert 'ns1' in content
    assert '<strong>Totals</strong>' in content
