from __future__ import annotations
import sqlite3
import os
import json
from dataclasses import dataclass
from typing import Optional, Iterable, Tuple, List
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS workload (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cluster TEXT NOT NULL,
  api_version TEXT NOT NULL,
  kind TEXT NOT NULL,
  namespace TEXT NOT NULL,
  name TEXT NOT NULL,
  resource_version TEXT,
  uid TEXT,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  manifest_json TEXT NOT NULL,
  manifest_hash TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS workload_identity ON workload(cluster, kind, namespace, name);
CREATE INDEX IF NOT EXISTS workload_hash ON workload(manifest_hash);
CREATE INDEX IF NOT EXISTS workload_deleted ON workload(deleted);
CREATE TABLE IF NOT EXISTS node_capacity (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cluster TEXT NOT NULL,
  node_name TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  cpu_capacity TEXT,
  memory_capacity TEXT,
  storage_capacity TEXT,
  pods_capacity TEXT,
  cpu_allocatable TEXT,
  memory_allocatable TEXT,
  storage_allocatable TEXT,
  pods_allocatable TEXT,
  node_role TEXT,
  instance_type TEXT,
  zone TEXT,
  os_image TEXT,
  kernel_version TEXT,
  container_runtime TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS node_capacity_identity ON node_capacity(cluster, node_name);
CREATE INDEX IF NOT EXISTS node_capacity_deleted ON node_capacity(deleted);
CREATE TABLE IF NOT EXISTS cluster_meta (
  cluster TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT,
  PRIMARY KEY (cluster, key)
);
"""

@dataclass
class UpsertResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

class WorkloadDB:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.cursor()
        cur.execute('PRAGMA journal_mode=WAL;')
        cur.executescript(SCHEMA)
        self._conn.commit()
    @contextmanager
    def transaction(self):
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()
    def upsert_workload(self, cluster: str, api_version: str, kind: str, namespace: str, name: str,
                        resource_version: Optional[str], uid: Optional[str], manifest: dict,
                        manifest_hash: str, now: Optional[datetime] = None) -> Tuple[str, bool]:
        now_s = (now or datetime.now(timezone.utc)).isoformat()
        manifest_json = json.dumps(manifest, separators=(',', ':'), sort_keys=True)
        cur = self._conn.cursor()
        cur.execute("SELECT manifest_hash, deleted FROM workload WHERE cluster=? AND kind=? AND namespace=? AND name=?", (
            cluster, kind, namespace, name
        ))
        row = cur.fetchone()
        if row is None:
            try:
                cur.execute("""INSERT INTO workload(cluster, api_version, kind, namespace, name, resource_version, uid, first_seen, last_seen, deleted, manifest_json, manifest_hash)
                             VALUES(?,?,?,?,?,?,?,?,?,0,?,?)""",
                            (cluster, api_version, kind, namespace, name, resource_version, uid, now_s, now_s, manifest_json, manifest_hash))
                self._conn.commit()
                return ('inserted', True)
            except sqlite3.IntegrityError:
                cur.execute("SELECT manifest_hash, deleted FROM workload WHERE cluster=? AND kind=? AND namespace=? AND name= ?", (
                    cluster, kind, namespace, name
                ))
                row = cur.fetchone()
                if row is None:
                    raise
        old_hash, was_deleted = row
        if old_hash == manifest_hash:
            cur.execute("UPDATE workload SET last_seen=?, deleted=0 WHERE cluster=? AND kind=? AND namespace=? AND name=?", (
                now_s, cluster, kind, namespace, name
            ))
            self._conn.commit()
            return ('unchanged', was_deleted == 1)
        else:
            cur.execute("UPDATE workload SET api_version=?, resource_version=?, uid=?, last_seen=?, manifest_json=?, manifest_hash=?, deleted=0 WHERE cluster=? AND kind=? AND namespace=? AND name= ?", (
                api_version, resource_version, uid, now_s, manifest_json, manifest_hash, cluster, kind, namespace, name
            ))
            self._conn.commit()
            return ('updated', True)
    def mark_deleted(self, cluster: str, alive_keys: Iterable[Tuple[str,str,str]], kinds_scope: Optional[Iterable[str]] = None):
        alive_set = set(alive_keys)
        cur = self._conn.cursor()
        if kinds_scope:
            scope = tuple(set(kinds_scope))
            placeholders = ','.join(['?'] * len(scope))
            existing = cur.execute(
                f"SELECT kind, namespace, name FROM workload WHERE cluster=? AND kind IN ({placeholders})",
                (cluster, *scope)
            ).fetchall()
        else:
            existing = cur.execute("SELECT kind, namespace, name FROM workload WHERE cluster=?", (cluster,)).fetchall()
        removed = 0
        for k, ns, n in existing:
            if (k, ns, n) not in alive_set:
                cur.execute("DELETE FROM workload WHERE cluster=? AND kind=? AND namespace=? AND name=?", (cluster, k, ns, n))
                removed += 1
        self._conn.commit()
        return removed
    def cleanup_obsolete_kinds(self, cluster: str, obsolete_kinds: List[str]) -> int:
        if not obsolete_kinds:
            return 0
        cur = self._conn.cursor()
        placeholders = ','.join(['?'] * len(obsolete_kinds))
        count_query = f"SELECT COUNT(*) FROM workload WHERE cluster=? AND kind IN ({placeholders})"
        removed = cur.execute(count_query, (cluster, *obsolete_kinds)).fetchone()[0]
        if removed > 0:
            delete_query = f"DELETE FROM workload WHERE cluster=? AND kind IN ({placeholders})"
            cur.execute(delete_query, (cluster, *obsolete_kinds))
            self._conn.commit()
        return removed
    def summary(self, cluster: str) -> dict:
        cur = self._conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM workload WHERE cluster=?", (cluster,)).fetchone()[0]
        active = total
        by_kind = cur.execute("SELECT kind, COUNT(*) FROM workload WHERE cluster=? GROUP BY kind", (cluster,)).fetchall()
        node_summary = {}
        nodes = cur.execute("SELECT COUNT(*) FROM node_capacity WHERE cluster=? AND deleted=0", (cluster,)).fetchone()[0]
        if nodes > 0:
            total_cpu = cur.execute("""
                SELECT SUM(CAST(REPLACE(cpu_capacity, 'm', '') AS INTEGER)) 
                FROM node_capacity WHERE cluster=? AND deleted=0 AND cpu_capacity IS NOT NULL
            """, (cluster,)).fetchone()[0] or 0
            total_memory = cur.execute("""
                SELECT SUM(
                    CASE 
                        WHEN memory_capacity LIKE '%Ki' THEN CAST(REPLACE(memory_capacity, 'Ki', '') AS INTEGER) / 1024
                        WHEN memory_capacity LIKE '%Mi' THEN CAST(REPLACE(memory_capacity, 'Mi', '') AS INTEGER)
                        WHEN memory_capacity LIKE '%Gi' THEN CAST(REPLACE(memory_capacity, 'Gi', '') AS INTEGER) * 1024
                        ELSE 0
                    END
                ) FROM node_capacity WHERE cluster=? AND deleted=0 AND memory_capacity IS NOT NULL
            """, (cluster,)).fetchone()[0] or 0
            by_role = cur.execute("""
                SELECT node_role, COUNT(*) FROM node_capacity 
                WHERE cluster=? AND deleted=0 GROUP BY node_role
            """, (cluster,)).fetchall()
            node_summary = {
                'total_nodes': nodes,
                'total_cpu_millicores': total_cpu,
                'total_memory_mi': total_memory,
                'by_role': {role: count for role, count in by_role}
            }
        return {
            'total': total,
            'active': active,
            'by_kind': {k: c for k, c in by_kind},
            'nodes': node_summary
        }
    def purge_deleted_older_than(self, cluster: str, cutoff: datetime) -> int:
        return 0
    def upsert_node_capacity(self, cluster: str, node_name: str, node_data: dict, now: Optional[datetime] = None) -> Tuple[str, bool]:
        now_s = (now or datetime.now(timezone.utc)).isoformat()
        status = node_data.get('status', {})
        capacity = status.get('capacity', {})
        allocatable = status.get('allocatable', {})
        node_info = status.get('nodeInfo', {})
        metadata = node_data.get('metadata', {})
        labels = metadata.get('labels', {})
        node_role = 'worker'
        if 'node-role.kubernetes.io/master' in labels or 'node-role.kubernetes.io/control-plane' in labels:
            node_role = 'master'
        elif 'node-role.kubernetes.io/infra' in labels:
            node_role = 'infra'
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM node_capacity WHERE cluster=? AND node_name=? AND deleted=0", (cluster, node_name))
        row = cur.fetchone()
        if row is None:
            cur.execute("""INSERT INTO node_capacity(
                cluster, node_name, first_seen, last_seen, deleted, 
                cpu_capacity, memory_capacity, storage_capacity, pods_capacity,
                cpu_allocatable, memory_allocatable, storage_allocatable, pods_allocatable,
                node_role, instance_type, zone, os_image, kernel_version, container_runtime
            ) VALUES(?,?,?,?,0,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                cluster, node_name, now_s, now_s,
                capacity.get('cpu'), capacity.get('memory'), capacity.get('ephemeral-storage'), capacity.get('pods'),
                allocatable.get('cpu'), allocatable.get('memory'), allocatable.get('ephemeral-storage'), allocatable.get('pods'),
                node_role, labels.get('node.kubernetes.io/instance-type'), 
                labels.get('topology.kubernetes.io/zone'), node_info.get('osImage'),
                node_info.get('kernelVersion'), node_info.get('containerRuntimeVersion')
            ))
            self._conn.commit()
            return ('inserted', True)
        else:
            cur.execute("""UPDATE node_capacity SET 
                last_seen=?, cpu_capacity=?, memory_capacity=?, storage_capacity=?, pods_capacity=?,
                cpu_allocatable=?, memory_allocatable=?, storage_allocatable=?, pods_allocatable=?,
                node_role=?, instance_type=?, zone=?, os_image=?, kernel_version=?, container_runtime=?, deleted=0
                WHERE cluster=? AND node_name=?""", (
                now_s, capacity.get('cpu'), capacity.get('memory'), capacity.get('ephemeral-storage'), capacity.get('pods'),
                allocatable.get('cpu'), allocatable.get('memory'), allocatable.get('ephemeral-storage'), allocatable.get('pods'),
                node_role, labels.get('node.kubernetes.io/instance-type'), 
                labels.get('topology.kubernetes.io/zone'), node_info.get('osImage'),
                node_info.get('kernelVersion'), node_info.get('containerRuntimeVersion'),
                cluster, node_name
            ))
            self._conn.commit()
            return ('updated', True)
    def mark_nodes_deleted(self, cluster: str, alive_nodes: Iterable[str]):
        cur = self._conn.cursor()
        alive_set = set(alive_nodes)
        existing = cur.execute("SELECT node_name FROM node_capacity WHERE cluster=?", (cluster,)).fetchall()
        removed = 0
        for (node_name,) in existing:
            if node_name not in alive_set:
                cur.execute("DELETE FROM node_capacity WHERE cluster=? AND node_name=?", (cluster, node_name))
                removed += 1
        self._conn.commit()
        return removed
    def set_meta(self, cluster: str, key: str, value: str):
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO cluster_meta(cluster,key,value) VALUES(?,?,?) ON CONFLICT(cluster,key) DO UPDATE SET value=excluded.value",
            (cluster, key, value),
        )
        self._conn.commit()
    def get_meta(self, cluster: str, key: str) -> Optional[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT value FROM cluster_meta WHERE cluster=? AND key=?", (cluster, key))
        row = cur.fetchone()
        return row[0] if row else None
