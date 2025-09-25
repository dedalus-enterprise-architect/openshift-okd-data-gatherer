from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, Any, Iterable, Tuple, List
from ..persistence.db import WorkloadDB
from .normalize import normalize_manifest
from ..util.hash import sha256_of_manifest


class SyncStats:
    def __init__(self):
        self.inserted = 0
        self.updated = 0
        self.unchanged = 0
        self.deleted = 0

    def as_dict(self):
        return self.__dict__


class SyncEngine:
    def __init__(self, db: WorkloadDB, cluster: str):
        self.db = db
        self.cluster = cluster

    def sync_kind(self, api_version: str, kind: str, items: Iterable[Dict[str, Any]]):
        alive_keys: List[Tuple[str, str, str]] = []
        alive_nodes: List[str] = []
        now = datetime.now(timezone.utc)

        for item in items:
            meta = item.get('metadata', {})
            namespace = meta.get('namespace', '')  # Empty for cluster-scoped
            name = meta['name']

            # Handle nodes separately for capacity tracking
            if kind == 'Node':
                self.db.upsert_node_capacity(self.cluster, name, item, now)
                alive_nodes.append(name)

            # Always store the full manifest for all kinds including nodes
            norm = normalize_manifest(item)
            h = sha256_of_manifest(norm)
            status, changed = self.db.upsert_workload(
                cluster=self.cluster,
                api_version=api_version,
                kind=kind,
                namespace=namespace,
                name=name,
                resource_version=meta.get('resourceVersion'),
                uid=meta.get('uid'),
                manifest=norm,
                manifest_hash=h,
                now=now
            )
            alive_keys.append((kind, namespace, name))

        # Mark deleted nodes if this was a Node sync
        if kind == 'Node' and alive_nodes:
            self.db.mark_nodes_deleted(self.cluster, alive_nodes)

        return alive_keys

    def finalize(self, alive_keys: Iterable[Tuple[str, str, str]], kinds_scope: Iterable[str] | None = None):
        """Finalize a sync operation.

        Only delete rows for kinds explicitly included in kinds_scope (if provided).
        This avoids removing data for kinds whose fetch failed this run.
        """
        removed = self.db.mark_deleted(self.cluster, alive_keys, kinds_scope=kinds_scope)
        return removed

    def cleanup_kinds(self, cluster: str, obsolete_kinds: List[str]) -> int:
        """Remove all records for kinds that are no longer in the configuration.

        This ensures snapshot purity by cleaning up data for kinds that are
        no longer being synchronized.
        """
        return self.db.cleanup_obsolete_kinds(cluster, obsolete_kinds)
