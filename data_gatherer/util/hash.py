from __future__ import annotations
import hashlib, json
from typing import Any

def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(',', ':'))

def sha256_of_manifest(manifest: Any) -> str:
    return hashlib.sha256(canonical_json(manifest).encode('utf-8')).hexdigest()
