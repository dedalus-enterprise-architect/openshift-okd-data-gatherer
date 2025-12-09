#!/usr/bin/env python3
"""
Extended test for ConfigMap Java options with various naming patterns
"""
import tempfile
import os
from data_gatherer.persistence.db import WorkloadDB
from data_gatherer.reporting.containers_config_report import ContainerConfigurationReport

def test_java_opts_patterns():
    """Test various Java options naming patterns."""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, 'test.db')
        db = WorkloadDB(db_path)
        report = ContainerConfigurationReport()

        # Create ConfigMap with different Java options patterns
        configmap_manifest = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': 'java-patterns',
                'namespace': 'test-ns'
            },
            'data': {
                'JAVA_OPTS': '-Xmx2g -Xms512m',
                'JAVA_OPTIONS': '-server -Dprop=value',
                'java_opts': '-Xmx1g',  # lowercase
                'java_options': '-client',  # lowercase
                'CATALINA_JAVA_OPTS': '-XX:+UseG1GC',  # with prefix
                'MY_JAVA_OPTS': '-Dproperty=value',  # with prefix
                'JVM_OPTS': '-Xmx512m',  # JVM instead of JAVA
                'NOT_JAVA': 'should be ignored'
            }
        }

        db.upsert_workload(
            cluster='test-cluster',
            api_version='v1',
            kind='ConfigMap',
            namespace='test-ns',
            name='java-patterns',
            resource_version='123',
            uid='configmap-uid',
            manifest=configmap_manifest,
            manifest_hash='configmap-hash'
        )

        test_cases = [
            ('JAVA_OPTS', 'JAVA_OPTS', '-Xmx2g -Xms512m'),
            ('JAVA_OPTIONS', 'JAVA_OPTIONS', '-server -Dprop=value'),
            ('java_opts', 'java_opts', '-Xmx1g'),
            ('java_options', 'java_options', '-client'),
            ('CATALINA_JAVA_OPTS', 'CATALINA_JAVA_OPTS', '-XX:+UseG1GC'),
            ('MY_JAVA_OPTS', 'MY_JAVA_OPTS', '-Dproperty=value'),
        ]

        for env_name, config_key, expected_value in test_cases:
            print(f"\n=== Testing pattern: {env_name} -> {config_key} ===")
            
            # Test with configMapKeyRef
            container_def = {
                'name': 'app',
                'env': [
                    {
                        'name': env_name,
                        'valueFrom': {
                            'configMapKeyRef': {
                                'name': 'java-patterns',
                                'key': config_key
                            }
                        }
                    }
                ]
            }
            result = report._extract_java_opts(container_def, 'test-ns', db)
            print(f"Result: {result}")
            assert result == expected_value, f"Expected {expected_value}, got: {result}"

        # Test envFrom behavior - should find first matching Java option
        print(f"\n=== Testing envFrom (entire ConfigMap) ===")
        container_def = {
            'name': 'app',
            'envFrom': [
                {
                    'configMapRef': {
                        'name': 'java-patterns'
                    }
                }
            ]
        }
        result = report._extract_java_opts(container_def, 'test-ns', db)
        print(f"Result: {result}")
        # With envFrom, should find ALL Java-related options combined
        # The new behavior finds all Java parameters, not just the first one
        assert 'JAVA_OPTS=-Xmx2g -Xms512m' in result, f"Expected JAVA_OPTS in result, got: {result}"
        assert 'JAVA_OPTIONS=-server -Dprop=value' in result, f"Expected JAVA_OPTIONS in result, got: {result}"
        assert 'CATALINA_JAVA_OPTS=-XX:+UseG1GC' in result, f"Expected CATALINA_JAVA_OPTS in result, got: {result}"

        print("\n=== All Java options pattern tests passed! ===")

if __name__ == '__main__':
    test_java_opts_patterns()
