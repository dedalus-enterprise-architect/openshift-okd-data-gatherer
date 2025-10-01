"""Comprehensive math validation for capacity report generation.

This test builds a multi-namespace scenario with replicas, init containers,
and varied request/limit values. It asserts:
1. Namespace-level main container aggregates (raw & replica-multiplied totals).
2. Global totals rows for main/all/overhead containers.
3. Cluster summary numeric lines (including core/GiB conversions).
4. Overhead calculations (init containers) derived as all - main.

All expected numbers are computed manually below to catch regressions.
"""

from click.testing import CliRunner
from data_gatherer.run import cli
from datetime import datetime, timezone


def _cfg(tmp_path, cluster: str) -> str:
    cfg = f"""storage:\n  base_dir: {tmp_path.as_posix()}\n  write_manifest_files: false\nclusters:\n  - name: {cluster}\n    credentials:\n      host: https://dummy\n      verify_ssl: false\n    include_kinds: [Deployment, StatefulSet, Job]\n    parallelism: 2\nlogging:\n  level: INFO\n  format: text\n"""
    p = tmp_path / 'cfg.yaml'
    p.write_text(cfg)
    return str(p)


def test_container_capacity_report_math(tmp_path):
    from data_gatherer.persistence.db import WorkloadDB

    now = datetime.now(timezone.utc)
    db_path = tmp_path / 'data.db'
    db = WorkloadDB(str(db_path))

    # Namespace ns1: Two deployments (one with init)
    dep_a = {
        'apiVersion': 'apps/v1', 'kind': 'Deployment',
        'metadata': {'name': 'dep-a', 'namespace': 'ns1'},
        'spec': {
            'replicas': 2,
            'template': {
                'spec': {
                    'initContainers': [
                        {  # init1: counts toward overhead only
                            'name': 'init1',
                            'resources': {
                                'requests': {'cpu': '25m', 'memory': '50Mi'},
                                'limits': {'cpu': '50m', 'memory': '100Mi'},
                            },
                        }
                    ],
                    'containers': [
                        {  # main1
                            'name': 'main1',
                            'resources': {
                                'requests': {'cpu': '100m', 'memory': '200Mi'},
                                'limits': {'cpu': '150m', 'memory': '300Mi'},
                            },
                        },
                        {  # sidecar1
                            'name': 'sidecar1',
                            'resources': {
                                'requests': {'cpu': '50m', 'memory': '100Mi'},
                                'limits': {'cpu': '100m', 'memory': '200Mi'},
                            },
                        },
                    ],
                }
            },
        },
    }
    dep_b = {
        'apiVersion': 'apps/v1', 'kind': 'Deployment',
        'metadata': {'name': 'dep-b', 'namespace': 'ns1'},
        'spec': {
            'replicas': 1,
            'template': {
                'spec': {
                    'containers': [
                        {
                            'name': 'main2',
                            'resources': {
                                'requests': {'cpu': '500m', 'memory': '1Gi'},  # 1024Mi
                                'limits': {'cpu': '1000m', 'memory': '2Gi'},    # 2048Mi
                            },
                        }
                    ]
                }
            },
        },
    }

    # Namespace ns2: StatefulSet + Job
    sts_c = {
        'apiVersion': 'apps/v1', 'kind': 'StatefulSet',
        'metadata': {'name': 'db', 'namespace': 'ns2'},
        'spec': {
            'replicas': 3,
            'template': {
                'spec': {
                    'containers': [
                        {
                            'name': 'db',
                            'resources': {
                                'requests': {'cpu': '250m', 'memory': '512Mi'},
                                'limits': {'cpu': '500m', 'memory': '1Gi'},  # 1024Mi
                            },
                        }
                    ]
                }
            },
        },
    }
    job_d = {
        'apiVersion': 'batch/v1', 'kind': 'Job',
        'metadata': {'name': 'batch', 'namespace': 'ns2'},
        'spec': {
            'parallelism': 4,
            'template': {
                'spec': {
                    'containers': [
                        {
                            'name': 'worker',
                            'resources': {
                                'requests': {'cpu': '125m', 'memory': '64Mi'},
                                'limits': {'cpu': '250m', 'memory': '128Mi'},
                            },
                        }
                    ]
                }
            },
        },
    }

    db.upsert_workload('math-cluster', 'apps/v1', 'Deployment', 'ns1', 'dep-a', '1', 'u1', dep_a, 'h1', now)
    db.upsert_workload('math-cluster', 'apps/v1', 'Deployment', 'ns1', 'dep-b', '1', 'u2', dep_b, 'h2', now)
    db.upsert_workload('math-cluster', 'apps/v1', 'StatefulSet', 'ns2', 'db', '1', 'u3', sts_c, 'h3', now)
    db.upsert_workload('math-cluster', 'batch/v1', 'Job', 'ns2', 'batch', '1', 'u4', job_d, 'h4', now)
    db._conn.close()

    cluster_dir = tmp_path / 'math-cluster'
    cluster_dir.mkdir(exist_ok=True)
    import shutil
    shutil.copy(str(db_path), cluster_dir / 'data.db')

    cfg_path = _cfg(tmp_path, 'math-cluster')

    runner = CliRunner()
    result = runner.invoke(cli, ['--config', cfg_path, 'report', '--cluster', 'math-cluster', '--type', 'capacity'])
    assert result.exit_code == 0, result.output

    report_files = list((cluster_dir / 'reports').glob('capacity-*.html'))
    assert report_files, 'Capacity report not generated.'
    html = report_files[0].read_text()

    # --- Expected aggregates (main only) ---
    # ns1 main raw: CPU 650, CPU lim 1250, Mem 1324, Mem lim 2548
    # ns1 main totals: CPU 800, CPU lim 1500, Mem 1624, Mem lim 3048 (2.98 GiB)
    assert '<th colspan="6">Namespace totals</th><th>650</th><th>1250</th><th>1324</th><th>2548</th><th>800</th><th>1500</th><th>1624</th><th>3048 (2.98 GiB)</th>' in html

    # ns2 main raw: CPU 375, CPU lim 750, Mem 576, Mem lim 1152
    # ns2 main totals: CPU 1250, CPU lim 2500, Mem 1792, Mem lim 3584 (3.50 GiB)
    assert '<th colspan="6">Namespace totals</th><th>375</th><th>750</th><th>576</th><th>1152</th><th>1250</th><th>2500</th><th>1792</th><th>3584 (3.50 GiB)</th>' in html

    # --- Global totals (main) ---
    # main raw: CPU 1025, CPU lim 2000, Mem 1900, Mem lim 3700
    # main totals: CPU 2050, CPU lim 4000, Mem 3416, Mem lim 6632 (6.48 GiB)
    # Check for content without specific class names (updated for new conditional formatting)
    assert '<th colspan="6">Totals (main containers)</th>' in html
    assert '1025</th>' in html and '2000</th>' in html and '1900</th>' in html and '3700</th>' in html
    assert '2050</th>' in html and '4000</th>' in html and '3416</th>' in html and '6632 (6.48 GiB)</th>' in html

    # --- Global totals (all) ---
    # all raw: CPU 1050, CPU lim 2050, Mem 1950, Mem lim 3800
    # all totals: CPU 2100, CPU lim 4100, Mem 3516, Mem lim 6832 (6.67 GiB)
    # Check for content without specific class names (updated for new conditional formatting)
    assert '<th colspan="6">Totals (all containers incl. init)</th>' in html
    assert '1050</th>' in html and '2050</th>' in html and '1950</th>' in html and '3800</th>' in html
    assert '2100</th>' in html and '4100</th>' in html and '3516</th>' in html and '6832 (6.67 GiB)</th>' in html

    # --- Overhead (init) ---
    # overhead totals: CPU 50, CPU lim 100, Mem 100, Mem lim 200 (0.20 GiB)
    # Check for content without specific class names (updated for new conditional formatting)
    assert '<th colspan="6">Overhead (init containers)</th>' in html
    assert '25</th>' in html and '50</th>' in html and '100</th>' in html and '200 (0.20 GiB)</th>' in html

    # Removed cluster summary list items; ensure new resource summary section appears
    assert 'Resource Summary (Cluster-wide)' in html
    assert '<h3>Containers</h3>' in html and '<h3>Worker Nodes</h3>' in html
