import os
import tarfile
import json
import yaml
from data_gatherer.export.manifest import ManifestExporter

SAMPLE_ITEMS = [
    {'metadata': {'name': 'alpha', 'namespace': 'default'}, 'spec': {'x': 1}},
    {'metadata': {'name': 'beta', 'namespace': 'other'}, 'spec': {'y': 2}},
]


def test_export_json(tmp_path):
    exporter = ManifestExporter(str(tmp_path), fmt='json')
    written = exporter.export_kind('Deployment', SAMPLE_ITEMS, namespaced=True)
    assert written == 2
    assert (tmp_path / 'Deployment' / 'default' / 'alpha.json').exists()
    data = json.loads((tmp_path / 'Deployment' / 'default' / 'alpha.json').read_text())
    assert data['spec']['x'] == 1


def test_export_yaml(tmp_path):
    exporter = ManifestExporter(str(tmp_path), fmt='yaml')
    exporter.export_kind('Deployment', SAMPLE_ITEMS, namespaced=True)
    text = (tmp_path / 'Deployment' / 'other' / 'beta.yaml').read_text()
    loaded = yaml.safe_load(text)
    assert loaded['spec']['y'] == 2


def test_export_archive(tmp_path):
    archive_path = tmp_path / 'out' / 'manifests.tgz'
    exporter = ManifestExporter(str(tmp_path / 'ignored'), fmt='json', archive=str(archive_path))
    exporter.export_kind('Deployment', SAMPLE_ITEMS, namespaced=True)
    exporter.close()
    assert archive_path.exists()
    with tarfile.open(archive_path, 'r:gz') as tf:
        names = tf.getnames()
        # Expect both names with proper structure
        assert any(n.endswith('alpha.json') for n in names)
        alpha_member = next(m for m in tf.getmembers() if m.name.endswith('alpha.json'))
        f = tf.extractfile(alpha_member)
        content = json.loads(f.read().decode())
        assert content['spec']['x'] == 1
