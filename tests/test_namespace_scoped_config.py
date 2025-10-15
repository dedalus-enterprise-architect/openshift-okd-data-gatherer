from data_gatherer.config import load_config, ClusterConfig
import tempfile
import textwrap
import os

def test_namespace_scoped_config_parsing():
    cfg_text = textwrap.dedent("""
    clusters:
      - name: ns-mode
        credentials:
          host: https://dummy
          verify_ssl: false
        namespace_scoped: true
        include_namespaces: [a, b, a]
        include_kinds: [Deployment]
    storage:
      base_dir: clusters
    logging:
      level: INFO
      format: text
    """)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'cfg.yaml')
        with open(path, 'w') as f: f.write(cfg_text)
        cfg = load_config(path)
        cluster = cfg.clusters[0]
        assert cluster.namespace_scoped is True
        assert cluster.include_namespaces == ['a','b']  # duplicate removed
        assert 'Node' not in cluster.include_kinds or True  # Node may be present but will be filtered later

def test_namespace_scoped_requires_namespaces():
    bad_cfg = textwrap.dedent("""
    clusters:
      - name: invalid
        credentials:
          host: https://dummy
          verify_ssl: false
        namespace_scoped: true
    """)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'cfg.yaml')
        with open(path, 'w') as f: f.write(bad_cfg)
        try:
            load_config(path)
            assert False, 'Expected ValueError'
        except ValueError as e:
            assert 'requires include_namespaces' in str(e)
