"""
Integration test for unified containers report with real cluster data.
Tests the unified report against actual cluster data to ensure it provides value.
"""

import pytest
import os
from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.cluster.context import get_cluster_paths, open_cluster_db
from data_gatherer.reporting.containers_config_report import ContainerConfigurationReport
from data_gatherer.config import load_config


def test_containers_config_report_real_data_integration():
    """Test unified containers report with real cluster data to verify it's not empty and contains expected data."""
    config_path = 'config/config.yaml'
    if not os.path.exists(config_path):
        pytest.skip("Config file not found - skipping integration test")
    
    cfg = load_config(config_path)
    
    # Find available cluster
    cluster_name = None
    if hasattr(cfg, 'clusters') and cfg.clusters:
        cluster_name = cfg.clusters[0].name
    
    if not cluster_name:
        pytest.skip("No clusters configured - skipping integration test")
    
    # Check if cluster data exists
    try:
        paths = get_cluster_paths(cfg, cluster_name)
        if not os.path.exists(paths.db_path):
            pytest.skip(f"Cluster database not found at {paths.db_path} - skipping integration test")
        
        db = open_cluster_db(cfg, cluster_name)
    except Exception as e:
        pytest.skip(f"Could not open cluster database: {e}")
    
    # Generate unified containers report
    report = ContainerConfigurationReport()
    output_path = f"/tmp/test_containers_config_{cluster_name}.html"
    
    try:
        report.generate(db, cluster_name, output_path)
        
        # Verify report was generated
        assert os.path.exists(output_path)
        
        # Read report content
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic validations
        assert f"Container Configuration Report: {cluster_name}" in content
        assert "Complete container configuration analysis" in content
        
        # Check for proper HTML structure (not escaped)
        assert "<table " in content
        assert "<tr>" in content
        assert "<td>" in content
        assert "<th>" in content
        
        # Should not have escaped HTML
        assert "&lt;table" not in content
        assert "&lt;tr&gt;" not in content  
        
        # Check standard columns are present
        column_headers = [
            "Kind", "Namespace", "Name", "Container", "Type",
            "Replicas", "CPU_req_m", "CPU_lim_m", "Mem_req_Mi", "Mem_lim_Mi",
            "Readiness_Probe", "Image_Pull_Policy", "Node_Selectors", "Pod_Labels", "Java_Opts"
        ]
        
        for header in column_headers:
            assert header in content, f"Missing expected column header: {header}"
        
        # Count table rows to verify we have data
        import re
        tr_matches = re.findall(r'<tr>', content)
        # Should have at least header row + some data rows
        assert len(tr_matches) >= 2, f"Expected at least 2 table rows, got {len(tr_matches)}"
        
        # Check for legend
        assert "Legend" in content
        assert "Key Columns" in content
        assert "Container Types" in content
        
        # Validate that we have both main and init container types if they exist
        if "main" in content:
            print(f"✓ Found main containers in {cluster_name}")
        if "init" in content:
            print(f"✓ Found init containers in {cluster_name}")
            
        # Count containers mentioned in the summary
        container_count_match = re.search(r'Total containers:</strong> (\d+)', content)
        if container_count_match:
            container_count = int(container_count_match.group(1))
            print(f"✓ Report contains {container_count} containers from {cluster_name}")
            assert container_count > 0, "Report should contain at least one container"
        
        # Check for resource information
        resource_patterns = [
            r'\d+',  # Numbers for CPU/Memory values
            r'IfNotPresent|Always|Never',  # Image pull policies
            r'Not configured|configured',  # Probe configurations
        ]
        
        resource_found = False
        for pattern in resource_patterns:
            if re.search(pattern, content):
                resource_found = True
                break
        
        assert resource_found, "Report should contain resource or configuration information"
        
        print(f"✓ Unified containers report integration test passed for cluster: {cluster_name}")
        
    finally:
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)



