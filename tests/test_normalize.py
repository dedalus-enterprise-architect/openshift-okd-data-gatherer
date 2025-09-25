from data_gatherer.sync.normalize import normalize_manifest

def test_normalize_removes_status_and_metadata_noise():
    obj = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': 'demo',
            'namespace': 'default',
            'resourceVersion': '123',
            'managedFields': [],
            'annotations': {
                'kubectl.kubernetes.io/last-applied-configuration': '{}',
                'user.annotation/key': 'value'
            }
        },
        'status': {'replicas': 1},
        'spec': {'replicas': 1}
    }
    norm = normalize_manifest(obj)
    assert 'status' not in norm
    meta = norm['metadata']
    assert 'resourceVersion' not in meta
    assert 'managedFields' not in meta
    assert meta['annotations'] == {'user.annotation/key': 'value'}
