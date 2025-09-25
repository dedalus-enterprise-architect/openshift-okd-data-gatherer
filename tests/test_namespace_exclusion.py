from data_gatherer.config import AppConfig, ClusterConfig, StorageConfig, LoggingConfig, ClusterCredentials

def test_namespace_exclusion_patterns():
    c = ClusterConfig(
        name='demo',
        include_kinds=[],
        exclude_namespaces={'exact-ns'},
        exclude_namespace_patterns=['temp-*', 'scratch?'],
        ignore_system_namespaces=False
    )
    assert c.is_namespace_excluded('exact-ns')
    assert c.is_namespace_excluded('temp-123')
    assert c.is_namespace_excluded('scratch1')
    assert not c.is_namespace_excluded('other')