from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict

_STRIP_METADATA_FIELDS = {
    'managedFields', 'creationTimestamp', 'resourceVersion', 'uid', 'generation'
}
_SYSTEM_ANNOTATION_PREFIXES = (
    'kubectl.kubernetes.io/', 'deployment.kubernetes.io/', 'openshift.io/generated-by'
)

_REMOVE_TOP_LEVEL = {'status'}


def normalize_manifest(obj: Dict[str, Any]) -> Dict[str, Any]:
    base = deepcopy(obj)
    for k in list(base.keys()):
        if k in _REMOVE_TOP_LEVEL:
            base.pop(k, None)
    meta = base.get('metadata', {})
    # Remove noisy metadata fields
    for f in _STRIP_METADATA_FIELDS:
        meta.pop(f, None)
    # Filter annotations
    ann = meta.get('annotations') or {}
    filtered = {k: v for k, v in ann.items() if not any(k.startswith(p) for p in _SYSTEM_ANNOTATION_PREFIXES)}
    if filtered:
        meta['annotations'] = filtered
    elif 'annotations' in meta:
        meta.pop('annotations')
    return base
