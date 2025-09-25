from __future__ import annotations
"""High-level query helpers over the raw SQLite schema.

These helpers encapsulate SQL so the rest of the codebase avoids
embedding ad-hoc queries and tuple index access, improving reuse
and maintainability.
"""
from dataclasses import dataclass
from typing import List, Dict, Any
import json


@dataclass
class NodeRecord:
    cluster: str
    node_name: str
    node_role: str | None
    instance_type: str | None
    zone: str | None
    cpu_capacity: str | None
    memory_capacity: str | None
    storage_capacity: str | None
    pods_capacity: str | None
    cpu_allocatable: str | None
    memory_allocatable: str | None
    storage_allocatable: str | None
    pods_allocatable: str | None
    os_image: str | None
    kernel_version: str | None
    container_runtime: str | None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.node_name,
            'role': self.node_role or 'worker',
            'instance_type': self.instance_type,
            'zone': self.zone,
            'capacity': {
                'cpu': self.cpu_capacity,
                'memory': self.memory_capacity,
                'storage': self.storage_capacity,
                'pods': self.pods_capacity,
            },
            'allocatable': {
                'cpu': self.cpu_allocatable,
                'memory': self.memory_allocatable,
                'storage': self.storage_allocatable,
                'pods': self.pods_allocatable,
            },
            'system': {
                'os_image': self.os_image,
                'kernel_version': self.kernel_version,
                'container_runtime': self.container_runtime,
            }
        }


class NodeQueries:
    def __init__(self, db):
        # Expects WorkloadDB instance (using its _conn). We keep the attribute
        # name private but accept the small coupling for simplicity.
        self._conn = db._conn

    def list_active_nodes(self, cluster: str) -> List[NodeRecord]:
        cur = self._conn.cursor()
        rows = cur.execute(
            """
            SELECT cluster, node_name, node_role, instance_type, zone,
                   cpu_capacity, memory_capacity, storage_capacity, pods_capacity,
                   cpu_allocatable, memory_allocatable, storage_allocatable, pods_allocatable,
                   os_image, kernel_version, container_runtime
            FROM node_capacity
            WHERE cluster=? AND deleted=0
            ORDER BY node_role, node_name
            """,
            (cluster,)
        ).fetchall()
        return [NodeRecord(*r) for r in rows]


class WorkloadQueries:
    def __init__(self, db):
        self._db = db

    def get_cluster_version(self, cluster: str) -> str:
        """Get cluster version from ClusterVersion or fallback methods"""
        # First try to get ClusterVersion (OpenShift)
        query = """
            SELECT manifest_json 
            FROM workload 
            WHERE cluster = ? AND kind = 'ClusterVersion'
            LIMIT 1
        """
        row = self._db._conn.execute(query, [cluster]).fetchone()
        if row:
            try:
                manifest = json.loads(row[0])
                # Try to get version from status.desired.version
                version = manifest.get('status', {}).get('desired', {}).get('version')
                if version:
                    return f"OpenShift {version}"
            except:
                pass

        # Fallback: try to get from any Node's nodeInfo
        query = """
            SELECT manifest_json 
            FROM workload 
            WHERE cluster = ? AND kind = 'Node'
            LIMIT 1
        """
        row = self._db._conn.execute(query, [cluster]).fetchone()
        if row:
            try:
                manifest = json.loads(row[0])
                node_info = manifest.get('status', {}).get('nodeInfo', {})
                kube_version = node_info.get('kubeletVersion', '')
                if kube_version:
                    return f"Kubernetes {kube_version}"
            except:
                pass

        return "Version unavailable"
