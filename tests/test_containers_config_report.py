"""
Tests for unified containers report functionality.
"""

import pytest
from data_gatherer.reporting.containers_config_report import ContainerConfigurationReport
from data_gatherer.persistence.db import WorkloadDB
import tempfile
import os


def test_containers_config_report_generation(tmp_path):
    """Test that unified containers report generates correctly with real data."""
    # Create temporary database
    db_path = tmp_path / "test.db"
    db = WorkloadDB(str(db_path))
    
    # Insert test workload data
    test_manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "test-app",
            "namespace": "test-namespace",
            "labels": {
                "app": "test",
                "version": "1.0"
            }
        },
        "spec": {
            "replicas": 2,
            "template": {
                "metadata": {
                    "labels": {
                        "app": "test",
                        "pod": "label"
                    }
                },
                "spec": {
                    "nodeSelector": {
                        "node-type": "worker"
                    },
                    "containers": [
                        {
                            "name": "app-container",
                            "image": "test:latest",
                            "imagePullPolicy": "Always",
                            "resources": {
                                "requests": {
                                    "cpu": "100m",
                                    "memory": "128Mi"
                                },
                                "limits": {
                                    "cpu": "200m",
                                    "memory": "256Mi"
                                }
                            },
                            "readinessProbe": {
                                "timeoutSeconds": 5,
                                "initialDelaySeconds": 10
                            },
                            "env": [
                                {
                                    "name": "JAVA_OPTS",
                                    "value": "-Xmx128m -Xms64m"
                                }
                            ]
                        }
                    ],
                    "initContainers": [
                        {
                            "name": "init-container",
                            "image": "init:latest",
                            "imagePullPolicy": "IfNotPresent",
                            "resources": {
                                "requests": {
                                    "cpu": "50m",
                                    "memory": "64Mi"
                                }
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Insert test data
    db.upsert_workload(
        cluster='test-cluster',
        api_version='apps/v1',
        kind='Deployment',
        namespace='test-namespace',
        name='test-app',
        resource_version='123',
        uid='test-uid',
        manifest=test_manifest,
        manifest_hash='test-hash'
    )
    
    # Generate report
    report = ContainerConfigurationReport()
    output_path = tmp_path / "unified-containers-test.html"
    
    report.generate(db, "test-cluster", str(output_path))
    
    # Verify report was generated
    assert output_path.exists()
    
    # Read and verify report content
    content = output_path.read_text()
    
    # Check basic structure
    assert "Container Configuration Report" in content
    assert "test-cluster" in content
    assert "Complete container configuration analysis" in content
    
    # Check standard columns are present
    assert "Kind" in content
    assert "Namespace" in content
    assert "Name" in content
    assert "Container" in content
    assert "Type" in content
    assert "Image" in content
    
    # Check resource columns
    assert "CPU_req_m" in content
    assert "CPU_lim_m" in content
    assert "Mem_req_Mi" in content
    assert "Mem_lim_Mi" in content
    
    # Check diagnostic columns
    assert "Readiness_Probe" in content
    assert "Image_Pull_Policy" in content
    assert "Node_Selectors" in content
    assert "Pod_Labels" in content
    assert "Java_Parameters" in content
    
    # Check data content
    assert "Deployment" in content
    assert "test-namespace" in content
    assert "test-app" in content
    assert "app-container" in content
    assert "init-container" in content
    assert "main" in content
    assert "init" in content
    
    # Check image values
    assert "test:latest" in content  # Main container image
    assert "init:latest" in content  # Init container image
    
    # Check resource values
    assert "100" in content  # CPU request 100m
    assert "200" in content  # CPU limit 200m
    assert "128" in content  # Memory request 128Mi
    assert "256" in content  # Memory limit 256Mi
    
    # Check diagnostic values
    assert "5s (initial: 10s)" in content  # Readiness probe
    assert "Always" in content  # Image pull policy for main container
    assert "IfNotPresent" in content  # Image pull policy for init container
    assert "node-type=worker" in content  # Node selector
    assert "app=test" in content  # Pod labels
    assert "-Xmx128m" in content  # Java opts
    
    # Check legend is present
    assert "Legend" in content
    assert "Key Columns" in content
    assert "Container Types" in content


def test_containers_config_report_empty_data(tmp_path):
    """Test unified containers report with no data."""
    # Create empty database
    db_path = tmp_path / "empty.db"
    db = WorkloadDB(str(db_path))
    
    # Generate report
    report = ContainerConfigurationReport()
    output_path = tmp_path / "unified-containers-empty.html"
    
    report.generate(db, "empty-cluster", str(output_path))
    
    # Verify report was generated
    assert output_path.exists()
    
    # Read and verify report content
    content = output_path.read_text()
    
    # Check basic structure
    assert "Container Configuration Report" in content
    assert "empty-cluster" in content
    assert "No container workloads found" in content


def test_containers_config_report_registration():
    """Test that unified containers report is properly registered."""
    from data_gatherer.reporting.base import get_report_types, get_generator
    
    # Check report is registered
    report_types = get_report_types()
    assert "containers-config" in report_types
    
    # Check generator can be retrieved
    generator = get_generator("containers-config")
    assert isinstance(generator, ContainerConfigurationReport)
    assert generator.type_name == "containers-config"
    assert generator.file_extension == ".html"
    assert generator.filename_prefix == "containers-config-"


def test_containers_config_report_helper_methods():
    """Test unified containers report helper methods."""
    report = ContainerConfigurationReport()
    
    # Test readiness probe extraction
    container_with_probe = {
        "readinessProbe": {
            "timeoutSeconds": 3,
            "initialDelaySeconds": 15
        }
    }
    probe_result = report._extract_readiness_probe_timeout(container_with_probe)
    assert probe_result == "3s (initial: 15s)"
    
    container_without_probe = {}
    probe_result = report._extract_readiness_probe_timeout(container_without_probe)
    assert probe_result == "Not configured"
    
    # Test Java options extraction
    container_with_java = {
        "env": [
            {"name": "JAVA_OPTS", "value": "-Xmx512m"},
            {"name": "OTHER_VAR", "value": "other"}
        ]
    }
    # Create mock db and namespace for the method call
    from unittest.mock import Mock
    mock_db = Mock()
    java_result = report._extract_java_opts(container_with_java, "test-namespace", mock_db)
    assert java_result == "-Xmx512m"
    
    container_without_java = {
        "env": [
            {"name": "OTHER_VAR", "value": "other"}
        ]
    }
    java_result = report._extract_java_opts(container_without_java, "test-namespace", mock_db)
    assert java_result == "Not configured"
    
    # Test labels formatting
    labels = {"app": "test", "version": "1.0", "env": "prod"}
    labels_result = report._format_labels(labels)
    assert "app=test" in labels_result
    assert "version=1.0" in labels_result
    assert "env=prod" in labels_result
    
    empty_labels = {}
    labels_result = report._format_labels(empty_labels)
    assert labels_result == "None"
    
    # Test node selector formatting
    node_selector = {"node-type": "worker", "zone": "us-west"}
    selector_result = report._format_node_selector(node_selector)
    assert "node-type=worker" in selector_result
    assert "zone=us-west" in selector_result
    
    empty_selector = {}
    selector_result = report._format_node_selector(empty_selector)
    assert selector_result == "None"
