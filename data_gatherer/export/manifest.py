from __future__ import annotations
"""Manifest exporting utilities.

Encapsulates writing normalized resource manifests to the filesystem so the
sync logic does not directly manage file layout. This enables future export
targets (compression, object storage, diff indexing) with minimal changes.
"""
import os
import json
import tarfile
import io
from typing import Iterable, Dict, Any, Literal, Optional
import yaml


class ManifestExporter:
    def __init__(self, base_dir: str, enabled: bool = True, skip_if_exists: bool = False,
                 fmt: Literal['json','yaml'] = 'json', archive: Optional[str] = None):
        """Create exporter.

        fmt: output file format
        archive: if provided, create/append to a tar.gz at this path instead of loose files
        """
        self.base_dir = base_dir
        self.enabled = enabled
        self.skip_if_exists = skip_if_exists
        self.fmt = fmt
        self.archive_path = archive
        self._tar: tarfile.TarFile | None = None
        if self.enabled and not self.archive_path:
            os.makedirs(self.base_dir, exist_ok=True)

    def _open_archive(self):
        if self.archive_path and self._tar is None:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.archive_path), exist_ok=True)
            mode = 'w:gz' if not os.path.exists(self.archive_path) else 'a:gz'
            self._tar = tarfile.open(self.archive_path, mode)

    def _serialize(self, item: Dict[str, Any]) -> bytes:
        if self.fmt == 'json':
            return json.dumps(item, indent=2, sort_keys=True).encode('utf-8')
        else:
            return yaml.safe_dump(item, sort_keys=True).encode('utf-8')

    def export_kind(self, kind: str, items: Iterable[Dict[str, Any]], namespaced: bool):
        if not self.enabled:
            return 0
        self._open_archive()
        count = 0
        for item in items:
            meta = item.get('metadata', {})
            name = meta.get('name')
            if not name:
                continue
            if namespaced:
                ns = meta.get('namespace', 'default')
                rel_dir = os.path.join(kind, ns)
            else:
                rel_dir = kind
            ext = 'json' if self.fmt == 'json' else 'yaml'
            rel_path = os.path.join(rel_dir, f'{name}.{ext}')
            full_dir = os.path.join(self.base_dir, rel_dir)
            data = self._serialize(item)
            if self.archive_path:
                info = tarfile.TarInfo(rel_path)
                info.size = len(data)
                self._tar.addfile(info, io.BytesIO(data))
            else:
                os.makedirs(full_dir, exist_ok=True)
                full_path = os.path.join(full_dir, f'{name}.{ext}')
                if self.skip_if_exists and os.path.exists(full_path):
                    continue
                with open(full_path, 'wb') as f:
                    f.write(data)
            count += 1
        return count

    def close(self):
        if self._tar is not None:
            self._tar.close()
            self._tar = None
