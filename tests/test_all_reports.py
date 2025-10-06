import tempfile
import os
from unittest.mock import patch
from data_gatherer.run import cli
from data_gatherer.persistence.db import WorkloadDB
import click.testing


def test_report_all_flag():
    """Test that --all flag generates all report types."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create test config
        cfg_content = f'''storage:
  base_dir: {tmp_dir}
  write_manifest_files: false
clusters:
  - name: test-cluster
    credentials:
      host: https://dummy
      verify_ssl: false
    include_kinds: [Deployment]
    parallelism: 2
logging:
  level: INFO
  format: text
'''
        config_path = os.path.join(tmp_dir, 'config.yaml')
        with open(config_path, 'w') as f:
            f.write(cfg_content)
        
        # Create database with test data
        db_path = os.path.join(tmp_dir, 'test-cluster', 'data.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = WorkloadDB(db_path)
        
        # Insert minimal test data
        test_manifest = {
            'metadata': {'name': 'test-app', 'namespace': 'test-ns'},
            'spec': {
                'replicas': 1,
                'template': {
                    'spec': {
                        'containers': [{'name': 'test', 'image': 'test:latest'}]
                    }
                }
            }
        }
        
        db.upsert_workload(
            cluster='test-cluster',
            api_version='apps/v1',
            kind='Deployment',
            namespace='test-ns',
            name='test-app',
            resource_version='123',
            uid='test-uid',
            manifest=test_manifest,
            manifest_hash='test-hash'
        )
        
        # Test --all flag
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [
            '--config', config_path,
            'report', 
            '--cluster', 'test-cluster', 
            '--all'
        ])
        
        assert result.exit_code == 0
        output = result.output

        # Should mention generating each report type in new format
        assert '[test-cluster] Generating container-capacity (html)' in output
        assert '[test-cluster] Generating nodes (html)' in output
        assert '[test-cluster] Generating summary (html)' in output
        assert '[test-cluster] Generating containers-config (html)' in output
        assert '[test-cluster] Generating cluster-capacity (html)' in output

        # New summary section
        assert 'Summary:' in output
        assert 'Generated:' in output

        # Verify report files were created
        reports_dir = os.path.join(tmp_dir, 'test-cluster', 'reports')
        assert os.path.exists(reports_dir)

        files = os.listdir(reports_dir)
        report_types = ['container-capacity', 'nodes', 'summary', 'containers-config', 'cluster-capacity']
        for report_type in report_types:
            matching_files = [f for f in files if f.startswith(f'{report_type}-')]
            assert len(matching_files) == 1, (
                f"Expected 1 {report_type} report file, found {len(matching_files)}: {matching_files}"
            )


def test_report_all_flag_excel_format_skips_html_only():
    """--all with --format excel should only generate Excel-compatible reports and skip HTML-only ones."""
    import tempfile
    runner = click.testing.CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_content = f'''storage:\n  base_dir: {tmp_dir}\n  write_manifest_files: false\nclusters:\n  - name: test-cluster\n    credentials:\n      host: https://dummy\n      verify_ssl: false\n    include_kinds: [Deployment]\n    parallelism: 2\nlogging:\n  level: INFO\n  format: text\n'''
        config_path = os.path.join(tmp_dir, 'config.yaml')
        with open(config_path, 'w') as f:
            f.write(cfg_content)
        db_path = os.path.join(tmp_dir, 'test-cluster', 'data.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        WorkloadDB(db_path)
        out_dir = os.path.join(tmp_dir, 'custom-out')
        result = runner.invoke(cli, [
            '--config', config_path,
            'report', '--cluster', 'test-cluster', '--all', '--format', 'excel', '--out', out_dir
        ])
        assert result.exit_code == 0
        assert os.path.isdir(out_dir)
        files = os.listdir(out_dir)
        # Only Excel-compatible reports should be generated
        # The exact types may vary, but nodes and summary are HTML-only in current implementation
        assert any('container-capacity' in f and f.endswith('.xlsx') for f in files)
        assert any('containers-config' in f and f.endswith('.xlsx') for f in files)
        assert any('cluster-capacity' in f and f.endswith('.xlsx') for f in files)
        # HTML-only reports should not be present
        assert not any('nodes' in f for f in files)
        assert not any('summary' in f for f in files)
        # Output should mention skipping HTML-only reports
        output = result.output
        assert 'Skipping nodes: does not support excel format' in output
        assert 'Skipping summary: does not support excel format' in output
    """--all with --out directory and --format override should work."""
    import tempfile
    runner = click.testing.CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_content = f'''storage:\n  base_dir: {tmp_dir}\n  write_manifest_files: false\nclusters:\n  - name: test-cluster\n    credentials:\n      host: https://dummy\n      verify_ssl: false\n    include_kinds: [Deployment]\n    parallelism: 2\nlogging:\n  level: INFO\n  format: text\n'''
        config_path = os.path.join(tmp_dir, 'config.yaml')
        with open(config_path, 'w') as f: f.write(cfg_content)
        db_path = os.path.join(tmp_dir, 'test-cluster', 'data.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        WorkloadDB(db_path)
        out_dir = os.path.join(tmp_dir, 'custom-out')
        result = runner.invoke(cli, [
            '--config', config_path,
            'report', '--cluster', 'test-cluster', '--all', '--format', 'html', '--out', out_dir
        ])
        assert result.exit_code == 0
        assert os.path.isdir(out_dir)
        files = os.listdir(out_dir)
        # Expect 5 reports
        assert len(files) == 5
        # Each file should contain cluster name and type in filename
        assert any('container-capacity' in f for f in files)
        assert any('containers-config' in f for f in files)
        assert any('nodes' in f for f in files)
        assert any('summary' in f for f in files)
        assert any('cluster-capacity' in f for f in files)

 
def test_report_all_flag_excel_format_skips_html_only():
    """--all with --format excel should only generate Excel-compatible reports and skip HTML-only ones."""
    import tempfile
    runner = click.testing.CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_content = f'''storage:\n  base_dir: {tmp_dir}\n  write_manifest_files: false\nclusters:\n  - name: test-cluster\n    credentials:\n      host: https://dummy\n      verify_ssl: false\n    include_kinds: [Deployment]\n    parallelism: 2\nlogging:\n  level: INFO\n  format: text\n'''
        config_path = os.path.join(tmp_dir, 'config.yaml')
        with open(config_path, 'w') as f:
            f.write(cfg_content)
        db_path = os.path.join(tmp_dir, 'test-cluster', 'data.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        WorkloadDB(db_path)
        out_dir = os.path.join(tmp_dir, 'custom-out')
        result = runner.invoke(cli, [
            '--config', config_path,
            'report', '--cluster', 'test-cluster', '--all', '--format', 'excel', '--out', out_dir
        ])
        assert result.exit_code == 0
        assert os.path.isdir(out_dir)
        files = os.listdir(out_dir)
        # Only Excel-compatible reports should be generated
        # The exact types may vary, but nodes and summary are HTML-only in current implementation
        assert any('container-capacity' in f and f.endswith('.xlsx') for f in files)
        assert any('containers-config' in f and f.endswith('.xlsx') for f in files)
        assert any('cluster-capacity' in f and f.endswith('.xlsx') for f in files)
        # HTML-only reports should not be present
        assert not any('nodes' in f for f in files)
        assert not any('summary' in f for f in files)
        # Output should mention skipping HTML-only reports
        output = result.output
        assert 'Skipping nodes: does not support excel format' in output
        assert 'Skipping summary: does not support excel format' in output

def test_list_types_includes_all_reports():
    """Test that --list-types includes all available report types."""
    runner = click.testing.CliRunner()
    result = runner.invoke(cli, [
        'report', 
        '--cluster', 'dummy',
        '--list-types'
    ])
    
    assert result.exit_code == 0
    output = result.output
    
    # Should list all current report types
    assert 'container-capacity' in output
    assert 'containers-config' in output
    assert 'nodes' in output
    assert 'summary' in output
    assert 'cluster-capacity' in output
