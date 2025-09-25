from __future__ import annotations
"""Query helpers for workload table to avoid scattering raw SQL."""
from typing import List, Dict, Any


class WorkloadQueries:
    def __init__(self, db):
        self._conn = db._conn

    def list_by_kind(self, cluster: str, kind: str) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT namespace, name, api_version, manifest_json FROM workload WHERE cluster=? AND kind=?",
            (cluster, kind)
        ).fetchall()
        import json
        result = []
        for namespace, name, api_version, manifest_json in rows:
            result.append({
                'cluster': cluster,
                'kind': kind,
                'namespace': namespace,
                'name': name,
                'apiVersion': api_version,
                'manifest': json.loads(manifest_json)
            })
        return result

    def count_by_kind(self, cluster: str) -> Dict[str, int]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT kind, COUNT(*) FROM workload WHERE cluster=? GROUP BY kind",
            (cluster,)
        ).fetchall()
        return {k: c for k, c in rows}

    def list_all(self, cluster: str):
        """Return all workloads with parsed manifest ordered by kind, namespace, name."""
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT kind, namespace, name, api_version, manifest_json FROM workload WHERE cluster=? ORDER BY kind, namespace, name",
            (cluster,)
        ).fetchall()
        import json
        out = []
        for kind, namespace, name, api_version, manifest_json in rows:
            try:
                manifest = json.loads(manifest_json)
            except Exception:
                manifest = {'_raw': manifest_json}
            out.append({
                'kind': kind,
                'namespace': namespace,
                'name': name,
                'apiVersion': api_version,
                'manifest': manifest
            })
        return out

    def list_for_kinds(self, cluster: str, kinds: List[str]):
        if not kinds:
            return []
        placeholders = ','.join(['?'] * len(kinds))
        cur = self._conn.cursor()
        rows = cur.execute(
            f"SELECT kind, namespace, name, api_version, manifest_json FROM workload WHERE cluster=? AND kind IN ({placeholders}) ORDER BY kind, namespace, name",
            (cluster, *kinds)
        ).fetchall()
        import json
        out = []
        for kind, namespace, name, api_version, manifest_json in rows:
            try:
                manifest = json.loads(manifest_json)
            except Exception:
                manifest = {'_raw': manifest_json}
            out.append({
                'kind': kind,
                'namespace': namespace,
                'name': name,
                'apiVersion': api_version,
                'manifest': manifest
            })
        return out
