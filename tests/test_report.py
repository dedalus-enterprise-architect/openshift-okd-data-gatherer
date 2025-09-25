import os
import glob
from click.testing import CliRunner
from data_gatherer.run import cli, DB_FILENAME
from data_gatherer.persistence.db import WorkloadDB
from datetime import datetime, timezone
import tempfile


def _write_config(path: str, base_dir: str):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"""
clusters:
  - name: c1
    credentials:
      host: https://dummy
      verify_ssl: false
    include_kinds: [Deployment, Node]

storage:
  base_dir: {base_dir}
  write_manifest_files: false

logging:
  level: INFO
  format: text
""")


def _seed_db(base_dir: str):
    cluster_dir = os.path.join(base_dir, 'c1')
    os.makedirs(cluster_dir, exist_ok=True)
    db_path = os.path.join(cluster_dir, DB_FILENAME)
    db = WorkloadDB(db_path)
    now = datetime.now(timezone.utc)
    # Insert a deployment
    db.upsert_workload(
        cluster='c1', api_version='apps/v1', kind='Deployment', namespace='ns', name='app',
        resource_version='1', uid='u1', manifest={'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'app', 'namespace': 'ns'}},
        manifest_hash='hashA', now=now
    )
    # Insert a node
    db.upsert_workload(
        cluster='c1', api_version='v1', kind='Node', namespace='', name='node1',
        resource_version='2', uid='n1', manifest={'apiVersion': 'v1', 'kind': 'Node', 'metadata': {'name': 'node1'}},
        manifest_hash='hashNode', now=now
    )
    return db_path


def test_report_default_path():
  with tempfile.TemporaryDirectory() as tmp:
    config_path = os.path.join(tmp, 'config.yaml')
    base_dir = os.path.join(tmp, 'clusters')
    _write_config(config_path, base_dir)
    _seed_db(base_dir)
    runner = CliRunner()
    result = runner.invoke(cli, ['--config', config_path, 'report', '--cluster', 'c1'])
    assert result.exit_code == 0, result.output
    reports_dir = os.path.join(base_dir, 'c1', 'reports')
    files = glob.glob(os.path.join(reports_dir, 'summary-*.html'))
    assert len(files) == 1, f"Expected 1 report file, found {files}"
    content = open(files[0], 'r', encoding='utf-8').read()
    assert '<html>' in content.lower()
    assert 'Cluster report: c1'.lower() in content.lower() or 'Summary report: c1'.lower() in content.lower()
    assert '<h2>Summary</h2>' in content


def test_report_explicit_out():
  with tempfile.TemporaryDirectory() as tmp:
    config_path = os.path.join(tmp, 'config.yaml')
    base_dir = os.path.join(tmp, 'clusters')
    _write_config(config_path, base_dir)
    _seed_db(base_dir)
    out_file = os.path.join(tmp, 'custom.html')
    runner = CliRunner()
    result = runner.invoke(cli, ['--config', config_path, 'report', '--cluster', 'c1', '--out', out_file])
    assert result.exit_code == 0, result.output
    assert os.path.exists(out_file)
    content = open(out_file, 'r', encoding='utf-8').read()
    assert '<table' in content  # at least one table rendered
    assert 'Deployment' in content