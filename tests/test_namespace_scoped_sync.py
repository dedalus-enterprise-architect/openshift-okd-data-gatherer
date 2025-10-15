import json
import tempfile
import os
from click.testing import CliRunner
from data_gatherer.run import cli

class DummyResp:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

def test_namespace_scoped_sync(monkeypatch):
    calls = []
    def fake_call_api(self, url, method, response_type=None, _preload_content=False, auth_settings=None):
        # Expect namespaced paths
        assert '/namespaces/' in url, 'Expected namespaced API path'
        # Extract namespace between /namespaces/ and next /
        parts = url.split('/namespaces/')[1].split('/')
        namespace = parts[0]
        calls.append(namespace)
        payload = {'items': [{
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {'name': f'app-{namespace}', 'namespace': namespace, 'resourceVersion': '1', 'uid': f'uid-{namespace}'},
            'spec': {'replicas': 1, 'template': {'spec': {'containers': [{'name': 'c', 'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'}}}]}}}
        }]}
        return (DummyResp(payload), 200, {})

    monkeypatch.setattr('kubernetes.client.ApiClient.call_api', fake_call_api)

    cfg_text = f"""
clusters:
  - name: c1
    credentials:
      host: https://dummy
      verify_ssl: false
    namespace_scoped: true
    include_namespaces: [ns1, ns2]
    include_kinds: [Deployment]
storage:\n  base_dir: REPLACEME
logging:\n  level: INFO\n  format: text\n"""
    with tempfile.TemporaryDirectory() as td:
        cfg_path = os.path.join(td, 'cfg.yaml')
        cfg_text = cfg_text.replace('REPLACEME', td)
        with open(cfg_path, 'w') as f: f.write(cfg_text)
        runner = CliRunner()
        res = runner.invoke(cli, ['--config', cfg_path, 'init', '--cluster', 'c1'])
        assert res.exit_code == 0, res.output
        res = runner.invoke(cli, ['--config', cfg_path, 'sync', '--cluster', 'c1'])
        assert res.exit_code == 0, res.output
        assert set(calls) == {'ns1', 'ns2'}