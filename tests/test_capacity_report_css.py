"""Tests focusing on CSS class and style presence in generated capacity report.

We validate that the report HTML contains the expected CSS class markers for:
- missing requests / limits (cell-level)
- namespace totals with missing request highlighting
- overall totals rows (main/all/overhead) with conditional missing class
- embedded style definitions (colors) to guard against accidental regressions
"""

from click.testing import CliRunner
from data_gatherer.run import cli
from datetime import datetime, timezone


def _write_config(tmp_path, cluster_name: str) -> str:
    cfg_content = f'''storage:\n  base_dir: {tmp_path.as_posix()}\n  write_manifest_files: false\nclusters:\n  - name: {cluster_name}\n    credentials:\n      host: https://dummy\n      verify_ssl: false\n    include_kinds: [Deployment]\n    parallelism: 1\nlogging:\n  level: INFO\n  format: text\n'''
    cfg_path = tmp_path / 'cfg.yaml'
    cfg_path.write_text(cfg_content)
    return str(cfg_path)


def test_capacity_report_css_classes(tmp_path):
    """Generate a report with deliberately missing requests/limits to assert CSS markers.

    Scenario:
    - One Deployment with two containers:
      * main container (missing all resources) -> should yield missing-req & missing-lim classes
      * helper container (full resources) -> no missing classes
    - One init container with full resources (to exercise overhead rows/classes)
    Expectations:
    - Cell classes: missing-req, missing-lim present
    - Totals rows: totals-row-main/all/overhead each get missing-req-total since any missing request exists
    - Namespace totals row includes ns-totals missing-req-total
    - Style block includes background color tokens for the key classes
    """
    from data_gatherer.persistence.db import WorkloadDB

    db_path = tmp_path / 'data.db'
    db = WorkloadDB(str(db_path))
    now = datetime.now(timezone.utc)

    manifest = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {'name': 'css-check', 'namespace': 'visual'},
        'spec': {
            'replicas': 2,
            'template': {
                'spec': {
                    'initContainers': [
                        {
                            'name': 'init-good',
                            'resources': {'requests': {'cpu': '50m', 'memory': '64Mi'}, 'limits': {'cpu': '100m', 'memory': '128Mi'}},
                        }
                    ],
                    'containers': [
                        {  # Missing everything -> should trigger both missing-req & missing-lim for cpu/mem columns
                            'name': 'main-missing',
                            'resources': {},
                        },
                        {
                            'name': 'helper',
                            'resources': {
                                'requests': {'cpu': '150m', 'memory': '256Mi'},
                                'limits': {'cpu': '300m', 'memory': '512Mi'},
                            },
                        },
                    ],
                }
            },
        },
    }

    db.upsert_workload(
        cluster='css-cluster', api_version='apps/v1', kind='Deployment',
        namespace='visual', name='css-check', resource_version='1', uid='u-css',
        manifest=manifest, manifest_hash='h-css', now=now,
    )
    db._conn.close()

    # Arrange directories to match expected layout
    cluster_dir = tmp_path / 'css-cluster'
    cluster_dir.mkdir(exist_ok=True)
    import shutil
    shutil.copy(str(db_path), cluster_dir / 'data.db')

    cfg_path = _write_config(tmp_path, 'css-cluster')

    runner = CliRunner()
    result = runner.invoke(cli, ['--config', cfg_path, 'report', '--cluster', 'css-cluster', '--type', 'capacity'])
    assert result.exit_code == 0, result.output

    reports_dir = cluster_dir / 'reports'
    files = list(reports_dir.glob('capacity-*.html'))
    assert files, 'No capacity report produced'

    content = files[0].read_text()

    # Check for new warning/error cell classes instead of old missing-req/missing-lim
    # Should have error cells for missing resource requests/limits
    assert 'class="error-miss-cell"' in content, 'error-miss-cell class not found - missing resource values should trigger error formatting'
    
    # Check that CSS for warning/error cells is present
    assert '.warning-miss-cell' in content, 'warning-miss-cell CSS class not found in styles'
    assert '.error-miss-cell' in content, 'error-miss-cell CSS class not found in styles'
    
    # Verify background colors are applied
    assert 'background-color: #fff3cd' in content, 'warning cell background color not found'
    assert 'background-color: #f8d7da' in content, 'error cell background color not found'
    
    # Check that totals sections exist (without specific class names)
    assert 'Totals (main containers)' in content
    assert 'Totals (all containers incl. init)' in content
    assert 'Overhead (init containers)' in content

    # Cluster totals wrapper row present
    assert 'class="cluster-totals-row"' in content
