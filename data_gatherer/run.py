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
from .kube.client import load_kubeconfig, configure_from_credentials, resolve_kinds, list_resources, list_namespaced_resources
from .util import logging as log
from kubernetes import client as k8s_client
from typing import Any

DEFAULT_DATA_DIR = 'clusters'
DB_FILENAME = 'data.db'

def _get_file_extension(format_name: str, generator: Any) -> str:
    """Get appropriate file extension based on format."""
    if format_name == 'excel':
        return '.xlsx'
    elif format_name == 'html':
        return '.html'
    else:
        # Fallback to generator's default extension
        return getattr(generator, 'file_extension', '.html')

@click.group(add_help_option=False)
@click.option('--config', default='config/config.yaml', help='Config file path')
@click.pass_context
def cli(ctx, config):
    """Data gatherer CLI"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config

@cli.command(add_help_option=False)
@click.option('--cluster', 'clusters', multiple=True, help='Cluster name(s); repeat for multiple')
@click.option('--all-clusters', is_flag=True, help='Operate on all configured clusters')
@click.pass_context
def init(ctx, clusters, all_clusters):
    """Initialize storage for one or more clusters."""
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    if not clusters and not all_clusters:
        raise click.ClickException('Must specify at least one --cluster or use --all-clusters')
    cluster_list = [c.name for c in cfg.clusters] if all_clusters else list(clusters)
    results = []
    for cluster in cluster_list:
        try:
            get_cluster_cfg(cfg, cluster)
        except ValueError as e:
            raise click.ClickException(str(e))
        paths = get_cluster_paths(cfg, cluster)
        os.makedirs(paths.base_dir, exist_ok=True)
        WorkloadDB(paths.db_path)
        results.append({'cluster': cluster, 'db': paths.db_path})
        click.echo(f'Initialized storage for {cluster} at {paths.db_path}')
    if len(results) > 1:
        click.echo(json.dumps(results, indent=2))

@cli.command(add_help_option=False)
@click.option('--cluster', 'clusters', multiple=True)
@click.option('--all-clusters', is_flag=True, help='Show status for all configured clusters')
@click.pass_context
def status(ctx, clusters, all_clusters):
    """Show summary status for one or more clusters."""
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    if not clusters and not all_clusters:
        raise click.ClickException('Must specify at least one --cluster or use --all-clusters')
    cluster_list = [c.name for c in cfg.clusters] if all_clusters else list(clusters)
    out = {}
    for cluster in cluster_list:
        try:
            get_cluster_cfg(cfg, cluster)
        except ValueError as e:
            raise click.ClickException(str(e))
        paths = get_cluster_paths(cfg, cluster)
        if not os.path.exists(paths.db_path):
            out[cluster] = {'error': 'not initialized'}
            continue
        db = WorkloadDB(paths.db_path)
        out[cluster] = db.summary(cluster)
    click.echo(json.dumps(out if len(out) > 1 else next(iter(out.values())), indent=2))

def _fetch_kind_items(api_client, kind, api_version, plural, target, namespaced, namespace: str | None = None):
    if namespace:
        log.info('listing kind in namespace', kind=kind, namespace=namespace, api_version=api_version)
    else:
        log.info('listing kind cluster-wide', kind=kind, api_version=api_version, namespaced=namespaced)
    items = []
    try:
        if namespace:
            for item in list_namespaced_resources(api_client, api_version, plural, namespace):
                items.append(item)
        else:
            for item in list_resources(api_client, api_version, plural):
                if namespaced:
                    ns = item.get('metadata', {}).get('namespace', 'default')
                    if target.is_namespace_excluded(ns):
                        continue
                items.append(item)
        return kind, items, None
    except Exception as e:
        log.error('failed to fetch kind', kind=kind, namespace=namespace, error=str(e))
        return kind, [], str(e)

@cli.command(add_help_option=False)
@click.option('--cluster', 'clusters', multiple=True)
@click.option('--all-clusters', is_flag=True, help='Sync all configured clusters')
@click.option('--kind', multiple=True, help='Limit to specific kinds')
@click.pass_context
def sync(ctx, clusters, all_clusters, kind):
    """Synchronize workload manifests for one or more clusters."""
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    if not clusters and not all_clusters:
        raise click.ClickException('Must specify at least one --cluster or use --all-clusters')
    cluster_list = [c.name for c in cfg.clusters] if all_clusters else list(clusters)
    aggregate = {}
    for cluster in cluster_list:
        try:
            target = get_cluster_cfg(cfg, cluster)
        except ValueError as e:
            raise click.ClickException(str(e))
        paths = get_cluster_paths(cfg, cluster)
        if not os.path.exists(paths.db_path):
            raise click.ClickException(f'Cluster {cluster} not initialized. Run init first.')
        db = WorkloadDB(paths.db_path)
        engine = SyncEngine(db, cluster)
        include = list(kind) if kind else target.include_kinds
        kind_map = resolve_kinds(include)
        if not kind_map:
            raise click.ClickException(f'No resolvable kinds requested for cluster {cluster}.')
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
        manifests_dir = paths.manifests_dir
        exporter = ManifestExporter(manifests_dir, enabled=cfg.storage.write_manifest_files)
        skipped = []
        fetched_per_kind = {}
        errors = {}
        # Namespace-scoped mode transformation
        namespace_mode = getattr(target, 'namespace_scoped', False)
        include_namespaces = getattr(target, 'include_namespaces', None)
        if namespace_mode:
            if not include_namespaces:
                raise click.ClickException(f'Cluster {cluster} has namespace_scoped=true but no include_namespaces specified')
            # Filter out cluster-scoped kinds (namespaced flag false)
            filtered_kind_map = {k: v for k, v in kind_map.items() if v[2]}
            skipped_cluster_scoped = set(kind_map.keys()) - set(filtered_kind_map.keys())
            if skipped_cluster_scoped:
                log.warn('skipping cluster-scoped kinds in namespace-scoped mode', cluster=cluster, skipped=list(skipped_cluster_scoped))
            kind_map = filtered_kind_map
            # Expand tasks for each (kind, namespace)
            tasks = [(k, ns) for k in kind_map.keys() for ns in include_namespaces]
            max_workers = min(target.parallelism, len(tasks))
            log.info('starting parallel fetch (namespace-scoped)', cluster=cluster, max_workers=max_workers, total_tasks=len(tasks))
        else:
            max_workers = min(target.parallelism, len(kind_map))
            log.info('starting parallel fetch', cluster=cluster, max_workers=max_workers, total_kinds=len(kind_map))
        from .persistence.db import WorkloadDB as _DBFactory
        def _fetch_and_sync_cluster(single_kind: str):
            api_version, plural, namespaced = kind_map[single_kind]
            _, items, error = _fetch_kind_items(api_client, single_kind, api_version, plural, target, namespaced)
            if error:
                return {'kind': single_kind, 'error': error}
            thread_db = _DBFactory(paths.db_path)
            thread_engine = SyncEngine(thread_db, cluster)
            alive_keys = thread_engine.sync_kind(api_version, single_kind, items)
            thread_db._conn.close()
            return {'kind': single_kind, 'items': items, 'alive': alive_keys}

        def _fetch_and_sync_namespaced(single_kind: str, ns: str):
            api_version, plural, _ = kind_map[single_kind]
            _, items, error = _fetch_kind_items(api_client, single_kind, api_version, plural, target, True, namespace=ns)
            if error:
                return {'kind': single_kind, 'namespace': ns, 'error': error}
            thread_db = _DBFactory(paths.db_path)
            thread_engine = SyncEngine(thread_db, cluster)
            alive_keys = thread_engine.sync_kind(api_version, single_kind, items)
            thread_db._conn.close()
            return {'kind': single_kind, 'namespace': ns, 'items': items, 'alive': alive_keys}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            if namespace_mode:
                future_map = {executor.submit(_fetch_and_sync_namespaced, k, ns): (k, ns) for k, ns in tasks}
            else:
                future_map = {executor.submit(_fetch_and_sync_cluster, k): (k, None) for k in kind_map.keys()}
            for fut in as_completed(future_map):
                result = fut.result()
                kind_name = result['kind']
                ns = result.get('namespace')
                key_for_errors = f"{kind_name}/{ns}" if ns else kind_name
                if 'error' in result:
                    errors[key_for_errors] = result['error']
                    if not namespace_mode:
                        skipped.append(kind_name)
                    continue
                items = result['items']
                alive = result['alive']
                fetched_per_kind[kind_name] = fetched_per_kind.get(kind_name, 0) + len(items)
                all_alive.extend(alive)
                if kind_name not in successful_kinds:
                    successful_kinds.append(kind_name)
                if not items and not namespace_mode:
                    existing_dir = os.path.join(manifests_dir, kind_name)
                    if not (os.path.exists(existing_dir) and any(os.scandir(existing_dir))):
                        skipped.append(kind_name)
                if items:
                    # Get the actual namespaced flag for this kind
                    _, _, is_namespaced = kind_map[kind_name]
                    exporter.export_kind(kind_name, items, is_namespaced)
        removed = engine.finalize(all_alive, kinds_scope=successful_kinds)
        configured_kinds = set(target.include_kinds)
        current_summary = db.summary(cluster)
        existing_kinds = set(current_summary.get('by_kind', {}).keys())
        obsolete_kinds = existing_kinds - configured_kinds
        if obsolete_kinds:
            obsolete_removed = engine.cleanup_kinds(cluster, list(obsolete_kinds))
            removed += obsolete_removed
        summary = db.summary(cluster)
        summary['removed'] = removed
        summary['skipped_kinds'] = skipped
        summary['fetched_per_kind'] = fetched_per_kind
        if errors:
            summary['errors'] = errors
        aggregate[cluster] = summary
    click.echo(json.dumps(aggregate if len(aggregate) > 1 else next(iter(aggregate.values())), indent=2))

@cli.command(add_help_option=False)
@click.option('--cluster', 'clusters', multiple=True, help='Cluster name(s) to report on')
@click.option('--all-clusters', is_flag=True, help='Generate reports for all configured clusters')
@click.option('--type', 'report_type', default='summary', help='Report type (default: summary). Use --list-types to view all.')
@click.option('--format', 'output_format', default='html', help='Output format (html, excel). Default: html')
@click.option('--out', required=False, help='Explicit output file path or directory (single-cluster only). If a directory is given, a default filename will be generated inside it.')
@click.option('--all', is_flag=True, help='Generate all available report types')
@click.option('--list-types', is_flag=True, help='List available report types and exit')
@click.pass_context
def report(ctx, clusters, all_clusters, report_type, output_format, out, all, list_types):
    from datetime import datetime
    from .reporting.base import get_report_types, get_generator
    from .reporting import summary_report  # noqa: F401
    from .reporting import containers_config_report  # noqa: F401
    from .reporting import nodes_report  # noqa: F401
    from .reporting import cluster_capacity_report  # noqa: F401 registers 'cluster-capacity'
    if list_types:
        click.echo('Available report types:')
        for t in get_report_types():
            click.echo(f'  {t}')
        return
    if all and out:
        # Only raise error if --out is a file path, not a directory
        if not os.path.isdir(out):
            raise click.ClickException('--out must be a directory when used with --all flag.')
    if all and report_type != 'summary':
        raise click.ClickException('Cannot specify --type with --all flag.')
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    if not clusters and not all_clusters and not list_types:
        raise click.ClickException('Specify at least one --cluster or --all-clusters')
    cluster_list = [c.name for c in cfg.clusters] if all_clusters else list(clusters)
    # single cluster path below
    if len(cluster_list) == 1:
        cluster = cluster_list[0]
        try:
            get_cluster_cfg(cfg, cluster)
        except ValueError as e:
            raise click.ClickException(str(e))
        paths = get_cluster_paths(cfg, cluster)
        if not os.path.exists(paths.db_path):
            raise click.ClickException('Cluster not initialized. Run init first.')
        db = WorkloadDB(paths.db_path)
        if all:
            # Use --out as reports_dir if provided and is a directory
            if out and os.path.isdir(out):
                reports_dir = out
            else:
                reports_dir = os.path.join(cfg.storage.base_dir, cluster, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%dT%H%M%S')
            generated_reports = []
            available_types = get_report_types()
            for current_type in available_types:
                try:
                    generator = get_generator(current_type)
                    prefix = getattr(generator, 'filename_prefix', 'report-')
                    supported_formats = getattr(generator, 'supported_formats', ['html'])
                    # Use requested output_format if supported, else fallback to HTML
                    if output_format in supported_formats:
                        format_to_use = output_format
                    else:
                        format_to_use = 'html' if 'html' in supported_formats else supported_formats[0]
                    file_ext = _get_file_extension(format_to_use, generator)
                    current_out = os.path.join(reports_dir, f'{prefix}{ts}{file_ext}')
                    click.echo(f'Generating {current_type} report...')
                    if format_to_use != output_format:
                        click.echo(f'  Skipping {current_type}: does not support {output_format} format')
                        continue
                    if hasattr(generator, 'supported_formats') and len(generator.supported_formats) > 1:
                        generator.generate(db, cluster, current_out, format_to_use)
                    else:
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
        
        # Validate format support
        supported_formats = getattr(generator, 'supported_formats', ['html'])
        if output_format not in supported_formats:
            raise click.ClickException(f'Report type {report_type} does not support format {output_format}. Supported: {", ".join(supported_formats)}')
        
        # If out is not provided, use default reports dir and filename
        if not out:
            reports_dir = os.path.join(cfg.storage.base_dir, cluster, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%dT%H%M%S')
            prefix = getattr(generator, 'filename_prefix', 'report-')
            file_ext = _get_file_extension(output_format, generator)
            out = os.path.join(reports_dir, f'{prefix}{ts}{file_ext}')
        else:
            # If out is a directory, construct default filename inside it
            if os.path.isdir(out):
                ts = datetime.now().strftime('%Y%m%dT%H%M%S')
                prefix = getattr(generator, 'filename_prefix', 'report-')
                file_ext = _get_file_extension(output_format, generator)
                out = os.path.join(out, f'{prefix}{ts}{file_ext}')
        # Call generate with format parameter if supported
        if hasattr(generator, 'supported_formats') and len(generator.supported_formats) > 1:
            generator.generate(db, cluster, out, output_format)
        else:
            generator.generate(db, cluster, out)
        click.echo(f'Wrote {report_type} report to {out}')
        return
    # multi-cluster path
    if out:
        raise click.ClickException('--out is only valid for single cluster usage')
    for cluster in cluster_list:
        try:
            get_cluster_cfg(cfg, cluster)
        except ValueError as e:
            raise click.ClickException(str(e))
        paths = get_cluster_paths(cfg, cluster)
        if not os.path.exists(paths.db_path):
            click.echo(f'Skipping {cluster}: not initialized')
            continue
        db = WorkloadDB(paths.db_path)
        reports_dir = os.path.join(cfg.storage.base_dir, cluster, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%dT%H%M%S')
        if all:
            types = get_report_types()
        else:
            types = [report_type]
        for t in types:
            try:
                generator = get_generator(t)
            except ValueError as e:
                click.echo(f'Skipping {cluster} report {t}: {e}')
                continue
            prefix = getattr(generator, 'filename_prefix', 'report-')
            # For multi-cluster, use specified format or default to HTML
            format_to_use = output_format if hasattr(generator, 'supported_formats') and output_format in generator.supported_formats else 'html'
            file_ext = _get_file_extension(format_to_use, generator)
            current_out = os.path.join(reports_dir, f'{prefix}{ts}{file_ext}')
            click.echo(f'[{cluster}] Generating {t} report...')
            try:
                if hasattr(generator, 'supported_formats') and len(generator.supported_formats) > 1:
                    generator.generate(db, cluster, current_out, format_to_use)
                else:
                    generator.generate(db, cluster, current_out)
                click.echo(f'[{cluster}] ✓ {t} -> {current_out}')
            except Exception as e:
                click.echo(f'[{cluster}] ✗ Failed {t}: {e}')

@cli.command(add_help_option=False)
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

@cli.command(add_help_option=False)
@click.option('--cluster', 'clusters', multiple=True)
@click.option('--all-clusters', is_flag=True, help='Show nodes for all configured clusters')
@click.pass_context
def nodes(ctx, clusters, all_clusters):
    """List node capacity info for one or more clusters."""
    config = ctx.obj['config']
    cfg = load_config(config)
    log.configure_logging(cfg.logging.level, cfg.logging.format)
    if not clusters and not all_clusters:
        raise click.ClickException('Must specify at least one --cluster or use --all-clusters')
    cluster_list = [c.name for c in cfg.clusters] if all_clusters else list(clusters)
    aggregate = []
    for cluster in cluster_list:
        try:
            get_cluster_cfg(cfg, cluster)
        except ValueError as e:
            raise click.ClickException(str(e))
        paths = get_cluster_paths(cfg, cluster)
        if not os.path.exists(paths.db_path):
            click.echo(f'Skipping {cluster}: not initialized')
            continue
        db = WorkloadDB(paths.db_path)
        nq = NodeQueries(db)
        node_records = nq.list_active_nodes(cluster)
        aggregate.append({'cluster': cluster, 'nodes': [n.to_dict() for n in node_records]})
    click.echo(json.dumps(aggregate if len(aggregate) > 1 else aggregate[0], indent=2))

@cli.command('help', add_help_option=False)
@click.argument('command', required=False)
@click.pass_context
def help_cmd(ctx, command):
    """Show context-driven help for a command, or list all commands."""
    group = ctx.parent.command if ctx.parent else ctx.command
    if not command:
        click.echo("Available commands:")
        for cmd_name in group.commands:
            click.echo(f"  {cmd_name}")
        click.echo("\nRun 'python -m data_gatherer.run help <command>' for details.")
        return
    cmd = group.commands.get(command)
    if not cmd:
        click.echo(f"Unknown command: {command}")
        click.echo("Run 'python -m data_gatherer.run help' to list available commands.")
        return
    with click.Context(cmd) as cmd_ctx:
        click.echo(cmd.get_help(cmd_ctx))

if __name__ == '__main__':
    cli()
