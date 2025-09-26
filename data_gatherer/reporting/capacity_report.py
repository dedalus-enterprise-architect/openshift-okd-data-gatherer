from __future__ import annotations
import html
from typing import List
from .base import ReportGenerator, register
from ..persistence.db import WorkloadDB
from ..persistence.workload_queries import WorkloadQueries
from .common import (
    CONTAINER_WORKLOAD_KINDS, cpu_to_milli, mem_to_mi,
    extract_pod_spec, get_replicas_for_workload,
    build_legend_html, wrap_html_document,
    format_cell_with_condition
)


@register
class CapacityReport(ReportGenerator):
    type_name = 'capacity'
    file_extension = '.html'
    filename_prefix = 'capacity-'

    def generate(self, db: WorkloadDB, cluster: str, out_path: str) -> None:  # pragma: no cover
        wq = WorkloadQueries(db)
        rows = wq.list_for_kinds(cluster, list(CONTAINER_WORKLOAD_KINDS))
        table_rows: List[List] = []
        main_cpu_raw = main_mem_raw = all_cpu_raw = all_mem_raw = 0
        main_cpu_total = main_mem_total = all_cpu_total = all_mem_total = 0
        main_cpu_lim_raw = main_mem_lim_raw = all_cpu_lim_raw = all_mem_lim_raw = 0
        main_cpu_lim_total = main_mem_lim_total = all_cpu_lim_total = all_mem_lim_total = 0
        for rec in rows:
            kind = rec['kind']
            namespace = rec['namespace']
            name = rec['name']
            manifest = rec['manifest']
            pod_spec = extract_pod_spec(kind, manifest)
            if not pod_spec:
                continue
            replicas = get_replicas_for_workload(kind, manifest) or 1
            containers = [(c, 'main') for c in pod_spec.get('containers', [])]
            containers += [(c, 'init') for c in pod_spec.get('initContainers', [])]
            for cdef, ctype in containers:
                resources = cdef.get('resources', {})
                req = resources.get('requests', {}) or {}
                lim = resources.get('limits', {}) or {}
                cpu_req = cpu_to_milli(req.get('cpu'))
                mem_req = mem_to_mi(req.get('memory'))
                cpu_lim = cpu_to_milli(lim.get('cpu'))
                mem_lim = mem_to_mi(lim.get('memory'))
                cpu_req_total = cpu_req * replicas if cpu_req is not None else ''
                mem_req_total = mem_req * replicas if mem_req is not None else ''
                cpu_lim_total = cpu_lim * replicas if cpu_lim is not None else ''
                mem_lim_total = mem_lim * replicas if mem_lim is not None else ''
                if cpu_req is not None:
                    all_cpu_raw += cpu_req
                    if isinstance(cpu_req_total, int):
                        all_cpu_total += cpu_req_total
                        if ctype == 'main':
                            main_cpu_raw += cpu_req
                            main_cpu_total += cpu_req_total
                if cpu_lim is not None:
                    all_cpu_lim_raw += cpu_lim
                    if isinstance(cpu_lim_total, int):
                        all_cpu_lim_total += cpu_lim_total
                        if ctype == 'main':
                            main_cpu_lim_raw += cpu_lim
                            main_cpu_lim_total += cpu_lim_total
                if mem_req is not None:
                    all_mem_raw += mem_req
                    if isinstance(mem_req_total, int):
                        all_mem_total += mem_req_total
                        if ctype == 'main':
                            main_mem_raw += mem_req
                            main_mem_total += mem_req_total
                if mem_lim is not None:
                    all_mem_lim_raw += mem_lim
                    if isinstance(mem_lim_total, int):
                        all_mem_lim_total += mem_lim_total
                        if ctype == 'main':
                            main_mem_lim_raw += mem_lim
                            main_mem_lim_total += mem_lim_total
                values = [
                    kind, namespace or '', name, cdef.get('name') or '', ctype,
                    replicas,
                    '' if cpu_req is None else cpu_req,
                    '' if cpu_lim is None else cpu_lim,
                    '' if mem_req is None else mem_req,
                    '' if mem_lim is None else mem_lim,
                    '' if isinstance(cpu_req_total, str) else cpu_req_total,
                    '' if isinstance(cpu_lim_total, str) else cpu_lim_total,
                    '' if isinstance(mem_req_total, str) else mem_req_total,
                    '' if isinstance(mem_lim_total, str) else mem_lim_total,
                ]
                # Append the row values only; legacy per-cell class markers (missing-req/missing-lim)
                # have been replaced by the unified rules engine based formatting handled in
                # format_cell_with_condition. Keeping data lean avoids confusion.
                table_rows.append(values)
        title = f"Capacity aggregation report: {html.escape(cluster)}"
        parts = [f"<h1>{title}</h1>"]
        # Legend now aligned with unified rules engine severities instead of legacy missing-req/missing-lim classes.
        # We still show structural row styles (totals) in a separate section for orientation.
        # Column legend (must cover every table header)
        capacity_legend_sections = [
            {
                'title': 'Columns',
                'items': [
                    'Kind: Workload controller kind (Deployment / StatefulSet / etc.)',
                    'Namespace: Kubernetes namespace (blank for cluster‑scoped)',
                    'Name: Workload name',
                    'Container: Container name inside pod spec',
                    'Type: Container type (main or init)',
                    'Replicas: Desired replicas (blank for DaemonSet)',
                    'CPU_req_m: CPU request (millicores)',
                    'CPU_lim_m: CPU limit (millicores)',
                    'Mem_req_Mi: Memory request (MiB)',
                    'Mem_lim_Mi: Memory limit (MiB)',
                    'CPU_req_m_total: CPU request * replicas (aggregated)',
                    'CPU_lim_m_total: CPU limit * replicas (aggregated)',
                    'Mem_req_Mi_total: Memory request * replicas (aggregated)',
                    'Mem_lim_Mi_total: Memory limit * replicas (aggregated)'
                ]
            },
            {
                'title': 'Configuration Severities',
                'items': [
                    {'class': 'error-miss-cell', 'description': 'Required value or parameter is missing'},
                    {'class': 'warning-miss-cell', 'description': 'Recommended value or parameter is missing'},
                    {'class': 'error-misconf-cell', 'description': 'Wrong value or parameter set'},
                    {'class': 'warning-misconf-cell', 'description': 'Value or parameter set should be re-evaluated'}
                ]
            },
            {
                'title': 'Structural Rows',
                'items': [
                    {'class': 'totals-row-main', 'description': 'Totals (main containers)'},
                    {'class': 'totals-row-all', 'description': 'Totals (all containers incl. init)'},
                    {'class': 'totals-row-overhead', 'description': 'Init container overhead'},
                    {'class': 'ns-totals', 'description': 'Per-namespace aggregated totals'}
                ]
            }
        ]
        parts.append(build_legend_html(capacity_legend_sections))
        parts.append("<h2>Resource Summary by Namespace</h2>")
        parts.append("<table border=1 cellpadding=4 cellspacing=0>")
        headers = [
            "Kind","Namespace","Name","Container","Type","Replicas",
            "CPU_req_m","CPU_lim_m","Mem_req_Mi","Mem_lim_Mi",
            "CPU_req_m_total","CPU_lim_m_total","Mem_req_Mi_total","Mem_lim_Mi_total"
        ]
        parts.append('<tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr>')
        from itertools import groupby
        table_rows_sorted = sorted(table_rows, key=lambda r: (r[1], r[0], r[2], r[3]))
        for ns, rows_group in groupby(table_rows_sorted, key=lambda r: r[1]):
            rows_list = list(rows_group)
            parts.append(f'<tr><td><strong>{html.escape(ns or "")}</strong></td>' + '<td colspan="13"></td></tr>')
            for row in rows_list:
                values = row[:-1] if len(row) > len(headers) else row
                cells = []
                for i, col in enumerate(values):
                    if i < len(headers):
                        row_data = {headers[j]: values[j] for j in range(min(len(headers), len(values)))}
                        cells.append(format_cell_with_condition(str(col), headers[i], row_data, 'capacity'))
                    else:
                        cells.append(f'<td>{html.escape(str(col))}</td>')
                parts.append('<tr>' + ''.join(cells) + '</tr>')
            if rows_list:
                ns_main_cpu_raw = sum((int(r[6]) for r in rows_list if r[4] == 'main' and r[6] != ''), 0)
                ns_main_cpu_lim_raw = sum((int(r[7]) for r in rows_list if r[4] == 'main' and r[7] != ''), 0)
                ns_main_mem_raw = sum((int(r[8]) for r in rows_list if r[4] == 'main' and r[8] != ''), 0)
                ns_main_mem_lim_raw = sum((int(r[9]) for r in rows_list if r[4] == 'main' and r[9] != ''), 0)
                ns_main_cpu_total = sum((int(r[10]) for r in rows_list if r[4] == 'main' and r[10] != ''), 0)
                ns_main_cpu_lim_total = sum((int(r[11]) for r in rows_list if r[4] == 'main' and r[11] != ''), 0)
                ns_main_mem_total = sum((int(r[12]) for r in rows_list if r[4] == 'main' and r[12] != ''), 0)
                ns_main_mem_lim_total = sum((int(r[13]) for r in rows_list if r[4] == 'main' and r[13] != ''), 0)
                ns_totals_cells = [
                    '<th colspan="6">Namespace totals</th>',
                    format_cell_with_condition(str(ns_main_cpu_raw), 'CPU_req_m', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                    format_cell_with_condition(str(ns_main_cpu_lim_raw), 'CPU_lim_m', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                    format_cell_with_condition(str(ns_main_mem_raw), 'Mem_req_Mi', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                    format_cell_with_condition(str(ns_main_mem_lim_raw), 'Mem_lim_Mi', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                    format_cell_with_condition(str(ns_main_cpu_total), 'CPU_req_m_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                    format_cell_with_condition(str(ns_main_cpu_lim_total), 'CPU_lim_m_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                    format_cell_with_condition(str(ns_main_mem_total), 'Mem_req_Mi_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                    format_cell_with_condition(f'{ns_main_mem_lim_total} ({ns_main_mem_lim_total/1024:.2f} GiB)', 'Mem_lim_Mi_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>')
                ]
                parts.append('<tr>' + ''.join(ns_totals_cells) + '</tr>')
        if table_rows:
            overhead_cpu_total = all_cpu_total - main_cpu_total
            overhead_mem_total = all_mem_total - main_mem_total
            overhead_cpu_cores = overhead_cpu_total / 1000
            overhead_mem_gib = overhead_mem_total / 1024
            main_totals_cells = [
                '<th colspan="6">Totals (main containers)</th>',
                format_cell_with_condition(str(main_cpu_raw), 'CPU_req_m', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(main_cpu_lim_raw), 'CPU_lim_m', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(main_mem_raw), 'Mem_req_Mi', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(main_mem_lim_raw), 'Mem_lim_Mi', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(main_cpu_total), 'CPU_req_m_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(main_cpu_lim_total), 'CPU_lim_m_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(main_mem_total), 'Mem_req_Mi_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(f'{main_mem_lim_total} ({main_mem_lim_total/1024:.2f} GiB)', 'Mem_lim_Mi_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>')
            ]
            parts.append('<tr>' + ''.join(main_totals_cells) + '</tr>')
            all_totals_cells = [
                '<th colspan="6">Totals (all containers incl. init)</th>',
                format_cell_with_condition(str(all_cpu_raw), 'CPU_req_m', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_cpu_lim_raw), 'CPU_lim_m', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_mem_raw), 'Mem_req_Mi', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_mem_lim_raw), 'Mem_lim_Mi', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_cpu_total), 'CPU_req_m_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_cpu_lim_total), 'CPU_lim_m_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_mem_total), 'Mem_req_Mi_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(f'{all_mem_lim_total} ({all_mem_lim_total/1024:.2f} GiB)', 'Mem_lim_Mi_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>')
            ]
            parts.append('<tr>' + ''.join(all_totals_cells) + '</tr>')
            overhead_totals_cells = [
                '<th colspan="6">Overhead (init containers)</th>',
                format_cell_with_condition(str(all_cpu_raw - main_cpu_raw), 'CPU_req_m', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_cpu_lim_raw - main_cpu_lim_raw), 'CPU_lim_m', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_mem_raw - main_mem_raw), 'Mem_req_Mi', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_mem_lim_raw - main_mem_lim_raw), 'Mem_lim_Mi', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(overhead_cpu_total), 'CPU_req_m_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(all_cpu_lim_total - main_cpu_lim_total), 'CPU_lim_m_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(str(overhead_mem_total), 'Mem_req_Mi_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>'),
                format_cell_with_condition(f'{all_mem_lim_total - main_mem_lim_total} ({(all_mem_lim_total - main_mem_lim_total)/1024:.2f} GiB)', 'Mem_lim_Mi_total', None, 'capacity').replace('<td', '<th').replace('</td>', '</th>')
            ]
            parts.append('<tr>' + ''.join(overhead_totals_cells) + '</tr>')
            parts.append('<tr class="cluster-totals-row"><td colspan="14">')
            parts.append('<h2>Cluster Totals</h2>')
            main_cpu_cores = main_cpu_total / 1000
            main_cpu_lim_cores = main_cpu_lim_total / 1000
            all_cpu_cores = all_cpu_total / 1000
            all_cpu_lim_cores = all_cpu_lim_total / 1000
            parts.append('<ul>')
            parts.append(f'<li><strong>Main containers (total requests CPU):</strong> {main_cpu_total} m ({main_cpu_cores:.2f} cores)</li>')
            parts.append(f'<li><strong>Main containers (total limits CPU):</strong> {main_cpu_lim_total} m ({main_cpu_lim_cores:.2f} cores)</li>')
            parts.append(f'<li><strong>Main containers (total memory):</strong> {main_mem_total/1024:.2f} GiB</li>')
            parts.append(f'<li><strong>Main containers (total limits memory):</strong> {main_mem_lim_total/1024:.2f} GiB</li>')
            parts.append(f'<li><strong>All containers (total requests CPU):</strong> {all_cpu_total} m ({all_cpu_cores:.2f} cores)</li>')
            parts.append(f'<li><strong>All containers (total limits CPU):</strong> {all_cpu_lim_total} m ({all_cpu_lim_cores:.2f} cores)</li>')
            parts.append(f'<li><strong>All containers (total memory):</strong> {all_mem_total/1024:.2f} GiB</li>')
            parts.append(f'<li><strong>All containers (total limits memory):</strong> {all_mem_lim_total/1024:.2f} GiB</li>')
            parts.append('</ul>')
            parts.append('<h3>Init Container Overhead</h3>')
            parts.append('<ul>')
            parts.append(f'<li><strong>CPU overhead:</strong> {overhead_cpu_total} m ({overhead_cpu_cores:.2f} cores)</li>')
            parts.append(f'<li><strong>Memory overhead:</strong> {overhead_mem_total} Mi ({overhead_mem_gib:.2f} GiB)</li>')
            parts.append('</ul>')
            parts.append('</td></tr>')
        parts.append('</table>')
        if not table_rows:
            parts.append('<p>No container workloads found for this cluster.</p>')
        additional_css = (
            " .totals-row-main th { background:#dfe; }"
            " .totals-row-all th { background:#def; }"
            " .totals-row-overhead th { background:#fed; }"
            " .ns-totals th { background:#f5f5f5; }"
            " .legend-box.totals-row-main { background: #dfe; }"
            " .legend-box.totals-row-all { background: #def; }"
            " .legend-box.totals-row-overhead { background: #fed; }"
            " .legend-box.ns-totals { background: #f5f5f5; }"
        )
        # Pass the additional CSS (structural row highlighting + legend swatches) into wrapper
        html_doc = wrap_html_document(title, parts, additional_css)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html_doc)
