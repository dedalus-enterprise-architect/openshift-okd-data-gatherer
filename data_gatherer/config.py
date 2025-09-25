from __future__ import annotations
import os
import yaml
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict
import fnmatch

DEFAULT_CONFIG_FILE = 'config.yaml'
DEFAULT_INCLUDE_KINDS = [
    'Deployment', 'StatefulSet', 'DaemonSet', 'CronJob', 'DeploymentConfig', 'Node'
]

@dataclass
class ClusterCredentials:
    host: str
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    verify_ssl: bool = True

@dataclass
class ClusterConfig:
    name: str
    kubeconfig: Optional[str] = None
    credentials: Optional[ClusterCredentials] = None
    include_kinds: List[str] = field(default_factory=lambda: list(DEFAULT_INCLUDE_KINDS))
    exclude_namespaces: Set[str] = field(default_factory=set)
    exclude_namespace_patterns: List[str] = field(default_factory=list)
    ignore_system_namespaces: bool = True
    parallelism: int = 4
    def is_namespace_excluded(self, namespace: str) -> bool:
        if namespace in self.exclude_namespaces:
            return True
        for pat in self.exclude_namespace_patterns:
            if fnmatch.fnmatch(namespace, pat):
                return True
        return False

@dataclass
class StorageConfig:
    base_dir: str = 'clusters'
    write_manifest_files: bool = True

@dataclass
class LoggingConfig:
    level: str = 'INFO'
    format: str = 'json'

@dataclass
class AppConfig:
    clusters: List[ClusterConfig]
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    system_namespaces_exact: Set[str] = field(default_factory=set)
    system_namespace_patterns: List[str] = field(default_factory=list)


def load_config(path: str = DEFAULT_CONFIG_FILE) -> AppConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(f'Config file not found: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}
    raw_system_namespaces = raw.get('system_namespaces', [])
    system_exact: Set[str] = set()
    system_patterns: List[str] = []
    for ns in raw_system_namespaces:
        if any(ch in ns for ch in ['*', '?', '[']):
            system_patterns.append(ns)
        else:
            system_exact.add(ns)
    clusters_data = raw.get('clusters', [])
    clusters: List[ClusterConfig] = []
    for c in clusters_data:
        raw_excludes = c.get('exclude_namespaces', [])
        ignore_system = c.get('ignore_system_namespaces', True)
        exact: Set[str] = set()
        patterns: List[str] = []
        for ns in raw_excludes:
            if any(ch in ns for ch in ['*', '?', '[']):
                patterns.append(ns)
            else:
                exact.add(ns)
        if ignore_system:
            exact.update(system_exact)
            for pat in system_patterns:
                if pat not in patterns:
                    patterns.append(pat)
        credentials = None
        creds_data = c.get('credentials')
        if creds_data:
            credentials = ClusterCredentials(
                host=creds_data['host'],
                token=creds_data.get('token'),
                username=creds_data.get('username'),
                password=creds_data.get('password'),
                cert_file=creds_data.get('cert_file'),
                key_file=creds_data.get('key_file'),
                ca_file=creds_data.get('ca_file'),
                verify_ssl=creds_data.get('verify_ssl', True)
            )
        clusters.append(ClusterConfig(
            name=c['name'],
            kubeconfig=c.get('kubeconfig'),
            credentials=credentials,
            include_kinds=c.get('include_kinds', list(DEFAULT_INCLUDE_KINDS)),
            exclude_namespaces=exact,
            exclude_namespace_patterns=patterns,
            ignore_system_namespaces=ignore_system,
            parallelism=c.get('parallelism', 4)
        ))
    if not clusters:
        raise ValueError('No clusters defined in configuration')
    for cluster in clusters:
        if not cluster.kubeconfig and not cluster.credentials:
            raise ValueError(f'Cluster {cluster.name} must specify either kubeconfig or credentials')
        if cluster.kubeconfig and cluster.credentials:
            raise ValueError(f'Cluster {cluster.name} cannot specify both kubeconfig and credentials')
        if cluster.credentials and not cluster.credentials.host:
            raise ValueError(f'Cluster {cluster.name} credentials must include host')
    storage_raw = raw.get('storage', {}) or {}
    storage = StorageConfig(
        base_dir=storage_raw.get('base_dir', 'clusters'),
        write_manifest_files=storage_raw.get('write_manifest_files', True)
    )
    logging_raw = raw.get('logging', {}) or {}
    logging_cfg = LoggingConfig(
        level=logging_raw.get('level', 'INFO'),
        format=logging_raw.get('format', 'json')
    )
    return AppConfig(
        clusters=clusters,
        storage=storage,
        logging=logging_cfg,
        system_namespaces_exact=system_exact,
        system_namespace_patterns=system_patterns
    )
