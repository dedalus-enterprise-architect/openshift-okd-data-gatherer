from __future__ import annotations
import click
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import load_config
from .persistence.db import WorkloadDB
from .cluster.context import get_cluster_cfg, get_cluster_paths, open_cluster_db
from .persistence.queries import NodeQueries
from .export.manifest import ManifestExporter
from .sync.engine import SyncEngine
from .kube.client import load_kubeconfig, configure_from_credentials, resolve_kinds, list_resources
from .util import logging as log
from kubernetes import client as k8s_client

DEFAULT_DATA_DIR = 'clusters'
DB_FILENAME = 'data.db'

@click.group()
@click.option('--config', default='config/config.yaml', help='Config file path')
@click.pass_context
def cli(ctx, config):
    """Data gatherer CLI"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config

@cli.command()
@click.option('--cluster', required=True, help='Cluster name to init')
@click.pass_context
def init(ctx, cluster):
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    try:
        target = get_cluster_cfg(cfg, cluster)
    except ValueError as e:
        raise click.ClickException(str(e))
    paths = get_cluster_paths(cfg, cluster)
    os.makedirs(paths.base_dir, exist_ok=True)
    WorkloadDB(paths.db_path)
    click.echo(f'Initialized storage at {paths.db_path}')

@cli.command()
@click.option('--cluster', required=True)
@click.pass_context
def status(ctx, cluster):
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    try:
        get_cluster_cfg(cfg, cluster)
    except ValueError as e:
        raise click.ClickException(str(e))
    paths = get_cluster_paths(cfg, cluster)
    if not os.path.exists(paths.db_path):
        raise click.ClickException('Cluster not initialized. Run init first.')
    db = WorkloadDB(paths.db_path)
    summary = db.summary(cluster)
    click.echo(json.dumps(summary, indent=2))

def _fetch_kind_items(api_client, kind, api_version, plural, target, namespaced):
    log.info('listing kind', kind=kind, api_version=api_version, namespaced=namespaced)
    items = []
    try:
        for item in list_resources(api_client, api_version, plural):
            if namespaced:
                ns = item.get('metadata', {}).get('namespace', 'default')
                if target.is_namespace_excluded(ns):
                    continue
            items.append(item)
        return kind, items, None
    except Exception as e:
        log.error('failed to fetch kind', kind=kind, error=str(e))
        return kind, [], str(e)

@cli.command()
@click.option('--cluster', required=True)
@click.option('--kind', multiple=True, help='Limit to specific kinds')
@click.pass_context
def sync(ctx, cluster, kind):
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    try:
        target = get_cluster_cfg(cfg, cluster)
    except ValueError as e:
        raise click.ClickException(str(e))
    paths = get_cluster_paths(cfg, cluster)
    if not os.path.exists(paths.db_path):
        raise click.ClickException('Cluster not initialized. Run init first.')
    db = WorkloadDB(paths.db_path)
    engine = SyncEngine(db, cluster)
    include = list(kind) if kind else target.include_kinds
    kind_map = resolve_kinds(include)
    if not kind_map:
        raise click.ClickException('No resolvable kinds requested.')
    if target.kubeconfig:
        load_kubeconfig(target.kubeconfig)
        api_client = k8s_client.ApiClient()
    elif target.credentials:
        config_obj = configure_from_credentials(target.credentials)
        api_client = k8s_client.ApiClient(configuration=config_obj)
    else:
        raise click.ClickException(f'Cluster {cluster} has no kubeconfig or credentials configured')
    all_alive = []
    successful_kinds = []
    paths = get_cluster_paths(cfg, cluster)
    manifests_dir = paths.manifests_dir
    exporter = ManifestExporter(manifests_dir, enabled=cfg.storage.write_manifest_files)
    skipped = []
    fetched_per_kind = {}
    errors = {}
    max_workers = min(target.parallelism, len(kind_map))
    log.info('starting parallel fetch', max_workers=max_workers, total_kinds=len(kind_map))
    from .persistence.db import WorkloadDB as _DBFactory
    def _fetch_and_sync(single_kind: str):
        api_version, plural, namespaced = kind_map[single_kind]
        kind_items_kind, items, error = _fetch_kind_items(api_client, single_kind, api_version, plural, target, namespaced)
        if error:
            return {'kind': single_kind, 'error': error}
        thread_db = _DBFactory(paths.db_path)
        thread_engine = SyncEngine(thread_db, cluster)
        alive_keys = thread_engine.sync_kind(api_version, single_kind, items)
        thread_db._conn.close()
        return {'kind': single_kind, 'items': items, 'alive': alive_keys}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_fetch_and_sync, k): k for k in kind_map.keys()}
        for fut in as_completed(future_map):
            result = fut.result()
            kind_name = result['kind']
            if 'error' in result:
                errors[kind_name] = result['error']
                skipped.append(kind_name)
                continue
            items = result['items']
            alive = result['alive']
            fetched_per_kind[kind_name] = len(items)
            all_alive.extend(alive)
            successful_kinds.append(kind_name)
            if not items:
                existing_dir = os.path.join(manifests_dir, kind_name)
                if not (os.path.exists(existing_dir) and any(os.scandir(existing_dir))):
                    skipped.append(kind_name)
            if items:
                _, _, is_namespaced = kind_map[kind_name]
                exporter.export_kind(kind_name, items, is_namespaced)
            log.debug('completed kind sync', kind=kind_name, items=len(items))
    removed = engine.finalize(all_alive, kinds_scope=successful_kinds)
    configured_kinds = set(target.include_kinds)
    current_summary = db.summary(cluster)
    existing_kinds = set(current_summary.get('by_kind', {}).keys())
    obsolete_kinds = existing_kinds - configured_kinds
    if obsolete_kinds:
        log.info('cleaning up obsolete kinds', obsolete_kinds=list(obsolete_kinds))
        obsolete_removed = engine.cleanup_kinds(cluster, list(obsolete_kinds))
        removed += obsolete_removed
    summary = db.summary(cluster)
    summary['removed'] = removed
    summary['skipped_kinds'] = skipped
    summary['fetched_per_kind'] = fetched_per_kind
    if errors:
        summary['errors'] = errors
    click.echo(json.dumps(summary, indent=2))

@cli.command()
@click.option('--cluster', required=True)
@click.option('--type', 'report_type', default='summary', help='Report type (default: summary). Use --list-types to view all.')
@click.option('--out', required=False, help='Explicit output file path (overrides auto-naming)')
@click.option('--all', is_flag=True, help='Generate all available report types')
@click.option('--list-types', is_flag=True, help='List available report types and exit')
@click.pass_context
def report(ctx, cluster, report_type, out, all, list_types):
    from datetime import datetime
    from .reporting.base import get_report_types, get_generator
    from .reporting import summary_report  # noqa: F401
    from .reporting import unified_containers_report  # noqa: F401
    from .reporting import nodes_report  # noqa: F401
    from .reporting import capacity_report  # noqa: F401
    if list_types:
        click.echo('Available report types:')
        for t in get_report_types():
            click.echo(f'  {t}')
        return
    if all and out:
        raise click.ClickException('Cannot specify --out with --all flag.')
    if all and report_type != 'summary':
        raise click.ClickException('Cannot specify --type with --all flag.')
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    try:
        get_cluster_cfg(cfg, cluster)
    except ValueError as e:
        raise click.ClickException(str(e))
    paths = get_cluster_paths(cfg, cluster)
    if not os.path.exists(paths.db_path):
        raise click.ClickException('Cluster not initialized. Run init first.')
    db = WorkloadDB(paths.db_path)
    if all:
        reports_dir = os.path.join(cfg.storage.base_dir, cluster, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%dT%H%M%S')
        generated_reports = []
        available_types = get_report_types()
        for current_type in available_types:
            try:
                generator = get_generator(current_type)
                prefix = getattr(generator, 'filename_prefix', 'report-')
                current_out = os.path.join(reports_dir, f'{prefix}{ts}{generator.file_extension}')
                click.echo(f'Generating {current_type} report...')
                generator.generate(db, cluster, current_out)
                generated_reports.append(current_out)
                click.echo(f'  ✓ Wrote {current_type} report to {current_out}')
            except Exception as e:
                click.echo(f'  ✗ Failed to generate {current_type} report: {e}')
                continue
        click.echo(f'\nGenerated {len(generated_reports)} reports successfully.')
        return
    try:
        generator = get_generator(report_type)
    except ValueError as e:
        raise click.ClickException(str(e))
    if not out:
        reports_dir = os.path.join(cfg.storage.base_dir, cluster, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%dT%H%M%S')
        prefix = getattr(generator, 'filename_prefix', 'report-')
        out = os.path.join(reports_dir, f'{prefix}{ts}{generator.file_extension}')
    generator.generate(db, cluster, out)
    click.echo(f'Wrote {report_type} report to {out}')

@cli.command()
@click.pass_context
def kinds(ctx):
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    from .kube.client import STATIC_KIND_MAP
    click.echo('Available workload kinds:')
    for kind, (api_version, plural, namespaced) in STATIC_KIND_MAP.items():
        scope = 'namespaced' if namespaced else 'cluster-scoped'
        click.echo(f'  {kind:18} {api_version:25} ({scope})')

@cli.command()
@click.option('--cluster', required=True)
@click.pass_context
def nodes(ctx, cluster):
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    try:
        get_cluster_cfg(cfg, cluster)
    except ValueError as e:
        raise click.ClickException(str(e))
    paths = get_cluster_paths(cfg, cluster)
    if not os.path.exists(paths.db_path):
        raise click.ClickException('Cluster not initialized. Run init first.')
    db = WorkloadDB(paths.db_path)
    nq = NodeQueries(db)
    node_records = nq.list_active_nodes(cluster)
    if not node_records:
        click.echo('No node data found. Run sync with Node kind included.')
        return
    result = {'cluster': cluster, 'nodes': []}
    for node in node_records:
        result['nodes'].append(node.to_dict())
    click.echo(json.dumps(result, indent=2))

if __name__ == '__main__':
    cli()
