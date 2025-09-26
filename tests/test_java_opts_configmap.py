#!/usr/bin/env python3
"""
Test ConfigMap Java options scanning functionality
"""
import tempfile
import os
import json
from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.reporting.containers_config_report import ContainerConfigurationReport

def test_java_opts_configmap_scanning():
    """Test that Java options are correctly extracted from ConfigMaps."""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        report = ContainerConfigurationReport()

        # Create ConfigMap with Java options
        configmap_manifest = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': 'java-config',
                'namespace': 'test-ns'
            },
            'data': {
                'JAVA_OPTS': '-Xmx2g -Xms512m -XX:+UseG1GC',
                'JAVA_OPTIONS': '-server -Dprop=value',
                'OTHER_CONFIG': 'not java related',
                'app.properties': 'config=value\njava.opts=-Xmx1g'
            }
        }

        # Store ConfigMap in database
        db.upsert_workload(
            cluster='test-cluster',
            api_version='v1',
            kind='ConfigMap',
            namespace='test-ns',
            name='java-config',
            resource_version='123',
            uid='configmap-uid',
            manifest=configmap_manifest,
            manifest_hash='configmap-hash'
        )

        print("=== Test 1: Direct env var with value ===")
        container_def = {
            'name': 'app',
            'env': [
                {'name': 'JAVA_OPTS', 'value': '-Xmx1g -Xms256m'}
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        print(f"Result: {result}")
        assert result == '-Xmx1g -Xms256m', f"Expected direct env value, got: {result}"

        print("\n=== Test 2: ConfigMapKeyRef ===")
        container_def = {
            'name': 'app',
            'env': [
                {
                    'name': 'JAVA_OPTS',
                    'valueFrom': {
                        'configMapKeyRef': {
                            'name': 'java-config',
                            'key': 'JAVA_OPTS'
                        }
                    }
                }
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        print(f"Result: {result}")
        assert result == '-Xmx2g -Xms512m -XX:+UseG1GC', f"Expected ConfigMap value, got: {result}"

        print("\n=== Test 3: ConfigMapKeyRef with different key ===")
        container_def = {
            'name': 'app',
            'env': [
                {
                    'name': 'JAVA_OPTIONS',
                    'valueFrom': {
                        'configMapKeyRef': {
                            'name': 'java-config',
                            'key': 'JAVA_OPTIONS'
                        }
                    }
                }
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        print(f"Result: {result}")
        assert result == '-server -Dprop=value', f"Expected ConfigMap JAVA_OPTIONS value, got: {result}"

        print("\n=== Test 4: envFrom configMapRef (entire ConfigMap) ===")
        container_def = {
            'name': 'app',
            'envFrom': [
                {
                    'configMapRef': {
                        'name': 'java-config'
                    }
                }
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        print(f"Result: {result}")
        # Should find the first Java-related key (JAVA_OPTS or JAVA_OPTIONS)
        assert result in ['-Xmx2g -Xms512m -XX:+UseG1GC', '-server -Dprop=value'], f"Expected ConfigMap Java value, got: {result}"

        print("\n=== Test 5: No Java options configured ===")
        container_def = {
            'name': 'app',
            'env': [
                {'name': 'OTHER_VAR', 'value': 'other-value'}
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        print(f"Result: {result}")
        assert result == 'Not configured', f"Expected 'Not configured', got: {result}"

        print("\n=== Test 6: ConfigMap not found ===")
        container_def = {
            'name': 'app',
            'env': [
                {
                    'name': 'JAVA_OPTS',
                    'valueFrom': {
                        'configMapKeyRef': {
                            'name': 'nonexistent-config',
                            'key': 'JAVA_OPTS'
                        }
                    }
                }
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        print(f"Result: {result}")
        assert result == 'Not configured', f"Expected 'Not configured', got: {result}"

        print("\n=== Test 7: ConfigMap key not found ===")
        container_def = {
            'name': 'app',
            'env': [
                {
                    'name': 'JAVA_OPTS',
                    'valueFrom': {
                        'configMapKeyRef': {
                            'name': 'java-config',
                            'key': 'NONEXISTENT_KEY'
                        }
                    }
                }
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        print(f"Result: {result}")
        assert result == 'Not configured', f"Expected 'Not configured', got: {result}"

        print("\n=== All ConfigMap Java options scanning tests passed! ===")

if __name__ == '__main__':
    test_java_opts_configmap_scanning()
