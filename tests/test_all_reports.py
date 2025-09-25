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
        
        # Should mention generating each report type
        assert 'Generating capacity report...' in output
        assert 'Generating nodes report...' in output
        assert 'Generating summary report...' in output
        assert 'Generating containers-config report...' in output
        
        # Should show successful generation
        assert 'Generated 4 reports successfully.' in output
        
        # Verify report files were created
        reports_dir = os.path.join(tmp_dir, 'test-cluster', 'reports')
        assert os.path.exists(reports_dir)
        
        files = os.listdir(reports_dir)
        report_types = ['capacity', 'nodes', 'summary', 'containers-config']
        
        for report_type in report_types:
            matching_files = [f for f in files if f.startswith(f'{report_type}-')]
            assert len(matching_files) == 1, f"Expected 1 {report_type} report file, found {len(matching_files)}: {matching_files}"


def test_report_all_flag_validation():
    """Test validation of --all flag with conflicting options."""
    runner = click.testing.CliRunner()
    
    # Test --all with --type should fail
    result = runner.invoke(cli, [
        'report', 
        '--cluster', 'test-cluster', 
        '--all', 
        '--type', 'containers'
    ])
    
    assert result.exit_code != 0
    assert 'Cannot specify --type with --all flag' in result.output
    
    # Test --all with --out should fail
    result = runner.invoke(cli, [
        'report', 
        '--cluster', 'test-cluster', 
        '--all', 
        '--out', '/tmp/report.html'
    ])
    
    assert result.exit_code != 0
    assert 'Cannot specify --out with --all flag' in result.output


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
    assert 'capacity' in output
    assert 'containers-config' in output
    assert 'nodes' in output
    assert 'summary' in output
