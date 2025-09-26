from __future__ import annotations
import html
import json
from .base import ReportGenerator, register
from ..persistence.db import WorkloadDB
from .common import wrap_html_document, format_cell_with_condition
from ..persistence.workload_queries import WorkloadQueries


@register
class SummaryReport(ReportGenerator):
    type_name = 'summary'
    file_extension = '.html'
    filename_prefix = 'summary-'

    def generate(self, db: WorkloadDB, cluster: str, out_path: str) -> None:  # pragma: no cover
        cur = db._conn.cursor()
        summary = db.summary(cluster)
        wq = WorkloadQueries(db)
        workloads = wq.list_all(cluster)
        nodes = cur.execute(
            """SELECT node_name, node_role, instance_type, zone, cpu_capacity, memory_capacity
                FROM node_capacity WHERE cluster=? ORDER BY node_role, node_name""",
            (cluster,)
        ).fetchall()
        title = f"Cluster report: {html.escape(cluster)}"
        parts = [f"<h1>{title}</h1>"]
        parts.append("""
        <div class="legend">
            <h3>Legend</h3>
            <div class="legend-section">
                <h4>Summary Items</h4>
                <ul>
                    <li><strong>Total workloads</strong>: Count of all rows in snapshot</li>
                    <li><strong>Active workloads</strong>: Same as total (snapshot only, non-deleted)</li>
                </ul>
            </div>
            <div class="legend-section">
                <h4>By Kind Table Columns</h4>
                <ul>
                    <li><strong>Kind</strong>: Workload controller kind</li>
                    <li><strong>Count</strong>: Number of workloads of that kind</li>
                </ul>
            </div>
            <div class="legend-section">
                <h4>Nodes Table Columns</h4>
                <ul>
                    <li><strong>Name</strong>: Node name</li>
                    <li><strong>Role</strong>: master / infra / worker (or other)</li>
                    <li><strong>Instance</strong>: Instance type</li>
                    <li><strong>Zone</strong>: Availability zone / failure domain</li>
                    <li><strong>CPU</strong>: Node CPU capacity (raw value)</li>
                    <li><strong>Memory</strong>: Node Memory capacity (raw value)</li>
                </ul>
            </div>
            <div class="legend-section">
                <h4>Workloads (Namespace Section)</h4>
                <ul>
                    <li><strong>details blocks</strong>: Expand to view full manifest JSON per workload</li>
                </ul>
            </div>
        </div>
        """)
        parts.append("<h2>Summary</h2>")
        parts.append("<ul>")
        parts.append(f"<li>Total workloads: {summary.get('total', 0)}</li>")
        parts.append(f"<li>Active workloads: {summary.get('active', 0)}</li>")
        parts.append("</ul>")
        parts.append("<h2>By kind</h2>")
        parts.append("<table border=1 cellpadding=4 cellspacing=0>")
        parts.append("<tr><th>Kind</th><th>Count</th></tr>")
        for k, c in (summary.get('by_kind') or {}).items():
            kind_cells = [
                f"<td>{html.escape(k)}</td>",
                format_cell_with_condition(str(c), "Count", None, 'summary')
            ]
            parts.append("<tr>" + "".join(kind_cells) + "</tr>")
        parts.append("</table>")
        parts.append("<h2>Nodes</h2>")
        if nodes:
            parts.append("<table border=1 cellpadding=4 cellspacing=0>")
            parts.append("<tr><th>Name</th><th>Role</th><th>Instance</th><th>Zone</th><th>CPU</th><th>Memory</th></tr>")
            headers = ["Name", "Role", "Instance", "Zone", "CPU", "Memory"]
            for n in nodes:
                node_cells = []
                for i, x in enumerate(n):
                    if i < len(headers):
                        row_data = {headers[j]: n[j] for j in range(min(len(headers), len(n)))}
                        node_cells.append(format_cell_with_condition(str(x) if x is not None else '', headers[i], row_data, 'summary'))
                    else:
                        node_cells.append(f"<td>{html.escape(str(x) if x is not None else '')}</td>")
                parts.append("<tr>" + "".join(node_cells) + "</tr>")
            parts.append("</table>")
        else:
            parts.append('<p>No node data available.</p>')
        parts.append("<h2>Workloads (by namespace)</h2>")
        if workloads:
            ns_map = {}
            for rec in workloads:
                kind = rec['kind']
                namespace = rec['namespace']
                name = rec['name']
                manifest = rec['manifest']
                ns_key = namespace or '(cluster-scoped)'
                ns_entry = ns_map.setdefault(ns_key, {})
                ns_entry.setdefault(kind, []).append((name, manifest, namespace))
            for ns in sorted(ns_map.keys()):
                parts.append(f'<h3>Namespace: {html.escape(ns)}</h3>')
                parts.append('<div>')
                for kind in sorted(ns_map[ns].keys()):
                    parts.append(f'<h4>{html.escape(kind)}</h4>')
                    for name, manifest, namespace in sorted(ns_map[ns][kind], key=lambda x: x[0]):
                        title_item = f"{kind} {namespace}/{name}" if namespace else f"{kind} {name}"
                        safe_title = html.escape(title_item)
                        try:
                            pretty = json.dumps(manifest, indent=2, sort_keys=True)
                        except Exception:
                            pretty = html.escape(str(manifest))
                        parts.append(f'<details><summary>{safe_title}</summary><pre>{html.escape(pretty)}</pre></details>')
                parts.append('</div>')
        else:
            parts.append('<p>No workloads found.</p>')
        additional_styles = ("pre { background: #f7f7f7; padding: 8px; overflow: auto; }")
        html_doc = wrap_html_document(title, parts, additional_styles)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html_doc)
