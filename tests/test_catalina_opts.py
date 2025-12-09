#!/usr/bin/env python3
"""
Test for CATALINA_OPTS detection (Tomcat Java parameters)
"""
import tempfile
import os
from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.reporting.containers_config_report import ContainerConfigurationReport


def test_catalina_opts_direct_env():
    """Test CATALINA_OPTS from direct env variable."""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        report = ContainerConfigurationReport()
        
        # Test CATALINA_OPTS alone (should return just the value)
        container_def = {
            'name': 'tomcat',
            'env': [
                {'name': 'CATALINA_OPTS', 'value': '-Xmx1g -Xms256m'}
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        assert result == '-Xmx1g -Xms256m', f"Expected CATALINA_OPTS value, got: {result}"
        print(f"✓ CATALINA_OPTS direct env: {result}")


def test_java_opts_and_catalina_opts_combined():
    """Test both JAVA_OPTS and CATALINA_OPTS together."""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        report = ContainerConfigurationReport()
        
        # Test both JAVA_OPTS and CATALINA_OPTS
        container_def = {
            'name': 'tomcat',
            'env': [
                {'name': 'JAVA_OPTS', 'value': '-Xmx2g -Xms512m'},
                {'name': 'CATALINA_OPTS', 'value': '-XX:+UseG1GC'}
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        # Should contain both parameters
        assert 'CATALINA_OPTS=-XX:+UseG1GC' in result, f"Expected CATALINA_OPTS in result, got: {result}"
        assert 'JAVA_OPTS=-Xmx2g -Xms512m' in result, f"Expected JAVA_OPTS in result, got: {result}"
        print(f"✓ Combined JAVA_OPTS and CATALINA_OPTS: {result}")


def test_catalina_opts_from_configmap():
    """Test CATALINA_OPTS from ConfigMap."""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        report = ContainerConfigurationReport()
        
        # Create ConfigMap with CATALINA_OPTS
        configmap_manifest = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': 'tomcat-config',
                'namespace': 'test-ns'
            },
            'data': {
                'CATALINA_OPTS': '-Djava.security.egd=file:/dev/./urandom'
            }
        }
        
        db.upsert_workload(
            cluster='test-cluster',
            api_version='v1',
            kind='ConfigMap',
            namespace='test-ns',
            name='tomcat-config',
            resource_version='123',
            uid='configmap-uid',
            manifest=configmap_manifest,
            manifest_hash='configmap-hash'
        )
        
        # Test with configMapKeyRef (should return just the value)
        container_def = {
            'name': 'tomcat',
            'env': [
                {
                    'name': 'CATALINA_OPTS',
                    'valueFrom': {
                        'configMapKeyRef': {
                            'name': 'tomcat-config',
                            'key': 'CATALINA_OPTS'
                        }
                    }
                }
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        assert result == '-Djava.security.egd=file:/dev/./urandom', f"Expected CATALINA_OPTS value, got: {result}"
        print(f"✓ CATALINA_OPTS from ConfigMap: {result}")


def test_catalina_opts_envfrom_configmap():
    """Test CATALINA_OPTS discovery from envFrom ConfigMap."""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        report = ContainerConfigurationReport()
        
        # Create ConfigMap with multiple Java options
        configmap_manifest = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': 'all-config',
                'namespace': 'test-ns'
            },
            'data': {
                'CATALINA_OPTS': '-Xmx1g',
                'JAVA_OPTS': '-Xmx2g',
                'OTHER_VAR': 'not-java'
            }
        }
        
        db.upsert_workload(
            cluster='test-cluster',
            api_version='v1',
            kind='ConfigMap',
            namespace='test-ns',
            name='all-config',
            resource_version='123',
            uid='configmap-uid',
            manifest=configmap_manifest,
            manifest_hash='configmap-hash'
        )
        
        # Test envFrom (should find both)
        container_def = {
            'name': 'tomcat',
            'envFrom': [
                {
                    'configMapRef': {
                        'name': 'all-config'
                    }
                }
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        # Should contain both CATALINA_OPTS and JAVA_OPTS
        assert 'CATALINA_OPTS' in result, f"Expected CATALINA_OPTS in result, got: {result}"
        assert 'JAVA_OPTS' in result, f"Expected JAVA_OPTS in result, got: {result}"
        print(f"✓ Multiple params from envFrom: {result}")


def test_is_java_param():
    """Test the _is_java_param helper method."""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        report = ContainerConfigurationReport()
        
        # Should match
        assert report._is_java_param('JAVA_OPTS')
        assert report._is_java_param('JAVA_OPTIONS')
        assert report._is_java_param('CATALINA_OPTS')
        assert report._is_java_param('MY_JAVA_OPTS')
        assert report._is_java_param('CUSTOM_JAVA_OPTIONS')
        
        # Should not match
        assert not report._is_java_param('PATH')
        assert not report._is_java_param('HOME')
        assert not report._is_java_param('OTHER_VAR')
        
        print("✓ _is_java_param() validation passed")


if __name__ == '__main__':
    test_catalina_opts_direct_env()
    test_java_opts_and_catalina_opts_combined()
    test_catalina_opts_from_configmap()
    test_catalina_opts_envfrom_configmap()
    test_is_java_param()
    print("\n=== All CATALINA_OPTS tests passed! ===")
