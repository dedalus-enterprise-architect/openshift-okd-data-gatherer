import json
from types import SimpleNamespace

from data_gatherer.kube.client import list_resources


class FakeApiClient:
    def __init__(self):
        self.calls = []

    def call_api(self, url, method, response_type=None, _preload_content=None, auth_settings=None, **kwargs):
        # Record call for assertions
        self.calls.append({
            'url': url,
            'method': method,
            'auth_settings': auth_settings,
        })
        # Return a minimal list response payload
        payload = {
            'apiVersion': 'v1',
            'kind': 'List',
            'items': [
                {'metadata': {'name': 'demo', 'namespace': 'default'}},
            ],
            'metadata': {'continue': ''}
        }
        data = json.dumps(payload).encode()
        return (SimpleNamespace(data=data), 200, {})


def test_list_resources_includes_auth_header():
    client = FakeApiClient()
    # Iterate to trigger the call
    items = list(list_resources(client, 'apps/v1', 'deployments'))
    # We expect exactly one recorded call
    assert client.calls, 'call_api was not invoked'
    call = client.calls[0]
    # Ensure auth settings include BearerToken so Authorization header is sent
    assert call['auth_settings'] == ['BearerToken']
    # And that we parsed items correctly
    assert len(items) == 1
    assert items[0]['metadata']['name'] == 'demo'
