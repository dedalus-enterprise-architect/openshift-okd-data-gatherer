"""Unified Containers Report combining resource and diagnostic data."""
from __future__ import annotations
from .base import ReportGenerator, register
from ..persistence.db import WorkloadDB
from ..persistence.workload_queries import WorkloadQueries
from .common import (
    CONTAINER_WORKLOAD_KINDS, cpu_to_milli, mem_to_mi,
    extract_pod_spec, get_replicas_for_workload,
    build_legend_html, get_common_legend_sections, wrap_html_document,
    format_cell_with_condition
)
import html


@register
class ContainerConfigurationReport(ReportGenerator):
    type_name = 'containers-config'
    file_extension = '.html'
    filename_prefix = 'containers-config-'

    def generate(self, db: WorkloadDB, cluster: str, out_path: str) -> None:
        wq = WorkloadQueries(db)
        rows = wq.list_for_kinds(cluster, list(CONTAINER_WORKLOAD_KINDS))
        table_rows = []
        for rec in rows:
            kind = rec['kind']
            namespace = rec['namespace']
            name = rec['name']
            manifest = rec['manifest']
            pod_spec = extract_pod_spec(kind, manifest)
            if not pod_spec:
                continue
            replicas = get_replicas_for_workload(kind, manifest)
            pod_labels = self._format_labels(
                (manifest.get('spec', {}).get('template', {}).get('metadata', {}).get('labels', {}))
            )
            node_selector = self._format_node_selector(pod_spec.get('nodeSelector', {}))
            containers = [(c, 'main') for c in pod_spec.get('containers', [])]
            containers += [(c, 'init') for c in pod_spec.get('initContainers', [])]
            for cdef, ctype in containers:
                container_name = cdef.get('name', 'Unknown')
                resources = cdef.get('resources', {})
                requests = resources.get('requests', {})
                limits = resources.get('limits', {})
                cpu_req = cpu_to_milli(requests.get('cpu'))
                cpu_lim = cpu_to_milli(limits.get('cpu'))
                mem_req = mem_to_mi(requests.get('memory'))
                mem_lim = mem_to_mi(limits.get('memory'))
                readiness_probe = self._extract_readiness_probe_timeout(cdef)
                image_pull_policy = cdef.get('imagePullPolicy', 'IfNotPresent')
                java_opts = self._extract_java_opts(cdef)
                row = [
                    kind,
                    namespace,
                    name,
                    container_name,
                    ctype,
                    str(replicas) if replicas is not None else '',
                    str(cpu_req) if cpu_req is not None else '',
                    str(cpu_lim) if cpu_lim is not None else '',
                    str(mem_req) if mem_req is not None else '',
                    str(mem_lim) if mem_lim is not None else '',
                    readiness_probe,
                    image_pull_policy,
                    node_selector,
                    pod_labels,
                    java_opts
                ]
                table_rows.append(row)
        title = f"Container Configuration Report: {html.escape(cluster)}"
        headers = [
            "Kind", "Namespace", "Name", "Container", "Type",
            "Replicas", "CPU_req_m", "CPU_lim_m", "Mem_req_Mi", "Mem_lim_Mi",
            "Readiness_Probe", "Image_Pull_Policy", "Node_Selectors", "Pod_Labels", "Java_Opts"
        ]
        html_content = self._build_html_document(title, headers, table_rows, cluster)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _extract_readiness_probe_timeout(self, container_def):
        readiness_probe = container_def.get('readinessProbe', {})
        if readiness_probe:
            timeout = readiness_probe.get('timeoutSeconds', 1)
            initial_delay = readiness_probe.get('initialDelaySeconds', 0)
            return f"{timeout}s (initial: {initial_delay}s)"
        return "Not configured"

    def _extract_java_opts(self, container_def):
        env = container_def.get('env', [])
        for env_var in env:
            var_name = env_var.get('name', '').upper()
            if 'JAVA' in var_name and 'OPT' in var_name:
                value = env_var.get('value', '')
                if value:
                    return value
        return "Not configured"

    def _format_labels(self, labels_dict):
        if not labels_dict:
            return "None"
        formatted_labels = [f"{k}={v}" for k, v in labels_dict.items()]
        return ", ".join(formatted_labels)

    def _format_node_selector(self, node_selector_dict):
        if not node_selector_dict:
            return "None"
        selectors = [f"{k}={v}" for k, v in node_selector_dict.items()]
        return ", ".join(selectors)

    def _build_html_document(self, title, headers, table_rows, cluster):
        parts = []
        parts.append(f'<h1>{title}</h1>')
        parts.append('<p>Complete container configuration analysis including resource allocation, health settings, and deployment configuration.</p>')
        legend_sections = get_common_legend_sections() + [
            {
                "title": "Key Columns",
                "items": [
                    "<strong>CPU_req_m/CPU_lim_m</strong>: CPU requests/limits in millicores",
                    "<strong>Mem_req_Mi/Mem_lim_Mi</strong>: Memory requests/limits in MiB",
                    "<strong>Readiness_Probe</strong>: Health check configuration",
                    "<strong>Image_Pull_Policy</strong>: Always/IfNotPresent/Never"
                ]
            }
        ]
        legend_html = build_legend_html(legend_sections)
        parts.append(legend_html)
        if not table_rows:
            parts.append('<p>No container workloads found.</p>')
        else:
            parts.append(f'<p><strong>Total containers:</strong> {len(table_rows)}</p>')
            parts.append('<table class="report-table">')
            parts.append('<thead><tr>')
            for header in headers:
                parts.append(f'<th>{html.escape(header)}</th>')
            parts.append('</tr></thead>')
            parts.append('<tbody>')
            for row in table_rows:
                parts.append('<tr>')
                for i, cell in enumerate(row):
                    cell_str = str(cell) if cell is not None else ''
                    if i < len(headers):
                        row_data = {headers[j]: row[j] for j in range(min(len(headers), len(row)))}
                        parts.append(format_cell_with_condition(cell_str, headers[i], row_data, 'containers'))
                    else:
                        parts.append(f'<td>{html.escape(cell_str)}</td>')
                parts.append('</tr>')
            parts.append('</tbody>')
            parts.append('</table>')
        return wrap_html_document(title, parts, self._get_unified_containers_css())

    def _get_unified_containers_css(self):
        return """
        .report-table { font-size: 12px; }
        .report-table th { position: sticky; top: 0; z-index: 10; }
        .report-table td { word-wrap: break-word; word-break: break-word; white-space: normal; }
        .report-table td:nth-child(1) { font-weight: bold; }
        .report-table td:nth-child(2) { font-family: monospace; }
        .report-table td:nth-child(3) { font-weight: 500; }
        .report-table td:nth-child(4) { font-family: monospace; }
        .report-table td:nth-child(5) { font-weight: bold; text-align: center; }
        .report-table td:nth-child(7),
        .report-table td:nth-child(8),
        .report-table td:nth-child(9),
        .report-table td:nth-child(10) { font-family: monospace; text-align: right; }
        .report-table td:nth-child(11) { font-size: 11px; }
        .report-table td:nth-child(12) { font-weight: 500; }
        .report-table td:nth-child(13) { font-size: 11px; }
        .report-table td:nth-child(14) { font-size: 10px; min-width: 200px; }
        .report-table td:nth-child(15) { font-family: monospace; font-size: 10px; min-width: 250px; }
        @media (max-width: 1400px) { .report-table { font-size: 11px; } .report-table td { padding: 6px; } .report-table td:nth-child(14), .report-table td:nth-child(15) { min-width: 150px; } }
        @media (max-width: 900px) { .report-table { display: block; overflow-x: auto; white-space: nowrap; } }
        </style>
        """
