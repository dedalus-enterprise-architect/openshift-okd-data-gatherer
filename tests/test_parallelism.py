import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from data_gatherer.run import _fetch_kind_items
from data_gatherer.config import ClusterConfig


def test_fetch_kind_items():
    """Test the parallel fetch function"""
    # Mock API client
    mock_api_client = MagicMock()
    
    # Mock list_resources to return test items
    test_items = [
        {
            'metadata': {
                'name': 'test-deployment',
                'namespace': 'default',
            },
            'spec': {'replicas': 1}
        },
        {
            'metadata': {
                'name': 'excluded-deployment', 
                'namespace': 'kube-system',
            },
            'spec': {'replicas': 1}
        }
    ]
    
    with patch('data_gatherer.run.list_resources', return_value=test_items):
        target = ClusterConfig(
            name='test',
            include_kinds=['Deployment'],
            exclude_namespaces={'kube-system'},
            exclude_namespace_patterns=[],
            ignore_system_namespaces=False
        )
        
        kind, items, error = _fetch_kind_items(
            mock_api_client, 'Deployment', 'apps/v1', 'deployments', target, True
        )
        
        assert kind == 'Deployment'
        assert error is None
        assert len(items) == 1  # One excluded due to namespace
        assert items[0]['metadata']['name'] == 'test-deployment'


def test_parallelism_configuration():
    """Test that parallelism config is properly loaded"""
    from data_gatherer.config import load_config
    
    config_content = """
clusters:
  - name: test
    kubeconfig: ~/.kube/config
    parallelism: 8
    include_kinds: [Deployment]

logging:
  level: DEBUG
  format: text
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        f.flush()
        
        try:
            cfg = load_config(f.name)
            assert len(cfg.clusters) == 1
            assert cfg.clusters[0].parallelism == 8
            assert cfg.logging.level == 'DEBUG'
            assert cfg.logging.format == 'text'
        finally:
            os.unlink(f.name)
