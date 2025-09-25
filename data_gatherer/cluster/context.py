from __future__ import annotations
from dataclasses import dataclass
import os
from ..config import AppConfig, ClusterConfig
from ..persistence.db import WorkloadDB

@dataclass(frozen=True)
class ClusterPaths:
    base_dir: str
    db_path: str
    manifests_dir: str
    reports_dir: str

def get_cluster_cfg(app_cfg: AppConfig, name: str) -> ClusterConfig:
    for c in app_cfg.clusters:
        if c.name == name:
            return c
    raise ValueError(f'Cluster {name} not found in config')

def get_cluster_paths(app_cfg: AppConfig, name: str) -> ClusterPaths:
    base = os.path.join(app_cfg.storage.base_dir, name)
    return ClusterPaths(
        base_dir=base,
        db_path=os.path.join(base, 'data.db'),
        manifests_dir=os.path.join(base, 'manifests'),
        reports_dir=os.path.join(base, 'reports'),
    )

def open_cluster_db(app_cfg: AppConfig, name: str, must_exist: bool = True) -> WorkloadDB:
    paths = get_cluster_paths(app_cfg, name)
    if must_exist and not os.path.exists(paths.db_path):
        raise FileNotFoundError('Cluster not initialized. Run init first.')
    return WorkloadDB(paths.db_path)
