from click.testing import CliRunner
from data_gatherer.run import cli
import json
import os


def test_list_report_types(tmp_path):
    # Copy config adjusting base_dir
    original = open('config/config.yaml').read().splitlines()
    modified = []
    for line in original:
        if line.strip().startswith('base_dir:'):
            modified.append(f'  base_dir: {tmp_path.as_posix()}')
        else:
            modified.append(line)
    cfg_local = tmp_path / 'config.yaml'
    cfg_local.write_text('\n'.join(modified))

    import yaml
    data = yaml.safe_load('\n'.join(modified))
    cluster_name = data['clusters'][0]['name']
    runner = CliRunner()
    res = runner.invoke(cli, ['--config', str(cfg_local), 'init', '--cluster', cluster_name])
    assert res.exit_code == 0, res.output

    res = runner.invoke(cli, ['--config', str(cfg_local), 'report', '--cluster', cluster_name, '--list-types'])
    assert res.exit_code == 0
    assert 'summary' in res.output
    assert 'containers' in res.output
    assert 'summary-json' not in res.output


def test_summary_report_and_removed_json(tmp_path):
    from data_gatherer.persistence.db import WorkloadDB
    db_path = tmp_path / 'data.db'
    db = WorkloadDB(str(db_path))
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    db.upsert_workload(
        cluster='c1', api_version='apps/v1', kind='Deployment', namespace='ns1', name='app1',
        resource_version='1', uid='u1', manifest={'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'app1', 'namespace': 'ns1'}},
        manifest_hash='h1', now=now
    )
    db._conn.close()
    cfg_content = f'''storage:\n  base_dir: {tmp_path.as_posix()}\n  write_manifest_files: false\nclusters:\n  - name: c1\n    credentials:\n      host: https://dummy\n      verify_ssl: false\n    include_kinds: [Deployment]\n    parallelism: 2\nlogging:\n  level: INFO\n  format: text\n'''
    cfg_path = tmp_path / 'cfg.yaml'
    cfg_path.write_text(cfg_content)
    cluster_dir = tmp_path / 'c1'
    cluster_dir.mkdir(exist_ok=True)
    import shutil
    import pathlib
    shutil.copy(str(db_path), cluster_dir / 'data.db')
    runner = CliRunner()
    # generate summary report
    res = runner.invoke(cli, ['--config', str(cfg_path), 'report', '--cluster', 'c1', '--type', 'summary'])
    assert res.exit_code == 0, res.output
    reports_dir = cluster_dir / 'reports'
    files = list(reports_dir.glob('summary-*.html'))
    assert files, 'No summary report produced'
    # attempt removed type
    res2 = runner.invoke(cli, ['--config', str(cfg_path), 'report', '--cluster', 'c1', '--type', 'summary-json'])
    assert res2.exit_code != 0


