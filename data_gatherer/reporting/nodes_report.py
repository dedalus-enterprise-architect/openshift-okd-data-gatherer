from __future__ import annotations
import html
from typing import Dict, List, Tuple, Optional
from .base import ReportGenerator, register
from ..persistence.db import WorkloadDB
from .common import wrap_html_document, format_cell_with_condition


def _parse_resource_value(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        value_str = str(value).lower()
        if value_str.endswith('m'):
            return float(value_str[:-1])
        elif value_str.endswith('n'):
            return float(value_str[:-1]) / 1_000_000
        elif value_str.endswith('u'):
            return float(value_str[:-1]) / 1_000
        else:
            return float(value_str) * 1000
    except (ValueError, AttributeError):
        try:
            if value_str.endswith('ki'):
                return float(value_str[:-2]) / 1024
            elif value_str.endswith('mi'):
                return float(value_str[:-2])
            elif value_str.endswith('gi'):
                return float(value_str[:-2]) * 1024
            elif value_str.endswith('ti'):
                return float(value_str[:-2]) * 1024 * 1024
            elif value_str.endswith('k'):
                return float(value_str[:-1]) / 1024
            elif value_str.endswith('m'):
                return float(value_str[:-1]) / (1024 * 1024)
            elif value_str.endswith('g'):
                return float(value_str[:-1]) * 1024
            else:
                return float(value_str) / (1024 * 1024)
        except (ValueError, AttributeError):
            return None
    return None


@register
class NodesReport(ReportGenerator):
    type_name = 'nodes'
    file_extension = '.html'
    filename_prefix = 'nodes-'

    def generate(self, db: WorkloadDB, cluster: str, out_path: str) -> None:
        cur = db._conn.cursor()
        nodes = cur.execute(
            """SELECT node_name, node_role, instance_type, zone, 
                      cpu_capacity, memory_capacity, cpu_allocatable, memory_allocatable
               FROM node_capacity 
               WHERE cluster=? AND deleted=0 
               ORDER BY node_role, node_name""",
            (cluster,)
        ).fetchall()
        if not nodes:
            self._generate_empty_report(cluster, out_path)
            return
        role_groups = self._group_nodes_by_role(nodes)
        title = f"Nodes resource report: {html.escape(cluster)}"
        parts = [f"<h1>{title}</h1>"]
        parts.append("""
        <div class="legend">
            <h3>Legend</h3>
            <div class="legend-section">
                <h4>Roles</h4>
                <ul>
                    <li><strong>master</strong>: Control plane</li>
                    <li><strong>infra</strong>: Infrastructure</li>  
                    <li><strong>worker</strong>: Application nodes</li>
                </ul>
            </div>
            <div class="legend-section">
                <h4>Resources</h4>
                <ul>
                    <li><strong>Capacity</strong>: Total node resources</li>
                    <li><strong>Allocatable</strong>: Available for pods</li>
                    <li><strong>Efficiency %</strong>: Allocatable/Capacity ratio</li>
                </ul>
            </div>
        </div>
        """)
        parts.extend(self._generate_summary_section(role_groups))
        for role in sorted(role_groups.keys()):
            parts.extend(self._generate_role_section(role, role_groups[role]))
        parts.extend(self._generate_cluster_totals(role_groups))
        additional_styles = (
            "table { width: 100%; }"
            "th { padding: 8px; text-align: left; }"
            "td { padding: 6px 8px; }"
            "h1 { color: #333; }"
            "h2 { color: #555; margin-top: 24px; }"
            "h3 { color: #777; margin-top: 20px; }"
            "ul { margin: 8px 0; }"
            "li { margin: 4px 0; }"
        )
        html_doc = wrap_html_document(title, parts, additional_styles)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html_doc)

    def _group_nodes_by_role(self, nodes: List[Tuple]) -> Dict[str, List[Dict]]:
        role_groups = {}
        for node_name, node_role, instance_type, zone, cpu_cap, mem_cap, cpu_alloc, mem_alloc in nodes:
            role = node_role or 'unknown'
            node_data = {
                'name': node_name,
                'instance_type': instance_type or 'unknown',
                'zone': zone or 'unknown',
                'cpu_capacity_m': _parse_resource_value(cpu_cap) or 0,
                'memory_capacity_mi': _parse_resource_value(mem_cap) or 0,
                'cpu_allocatable_m': _parse_resource_value(cpu_alloc) or 0,
                'memory_allocatable_mi': _parse_resource_value(mem_alloc) or 0,
            }
            if role not in role_groups:
                role_groups[role] = []
            role_groups[role].append(node_data)
        return role_groups

    def _generate_summary_section(self, role_groups: Dict[str, List[Dict]]) -> List[str]:
        parts = ["<h2>Resource Summary by Node Role</h2>"]
        parts.append("<table border=1 cellpadding=4 cellspacing=0>")
        parts.append("<tr><th>Role</th><th>Count</th><th>CPU Capacity (cores)</th><th>CPU Allocatable (cores)</th>"
                    "<th>Memory Capacity (GiB)</th><th>Memory Allocatable (GiB)</th><th>CPU Efficiency</th><th>Memory Efficiency</th></tr>")
        for role in sorted(role_groups.keys()):
            nodes = role_groups[role]
            count = len(nodes)
            total_cpu_cap = sum(node['cpu_capacity_m'] for node in nodes) / 1000
            total_cpu_alloc = sum(node['cpu_allocatable_m'] for node in nodes) / 1000
            total_mem_cap = sum(node['memory_capacity_mi'] for node in nodes) / 1024
            total_mem_alloc = sum(node['memory_allocatable_mi'] for node in nodes) / 1024
            cpu_efficiency = (total_cpu_alloc / total_cpu_cap * 100) if total_cpu_cap > 0 else 0
            mem_efficiency = (total_mem_alloc / total_mem_cap * 100) if total_mem_cap > 0 else 0
            row_cells = [
                f"<td><strong>{html.escape(role)}</strong></td>",
                format_cell_with_condition(str(count), "Count", None, 'nodes'),
                format_cell_with_condition(f"{total_cpu_cap:.1f}", "CPU_Capacity", None, 'nodes'),
                format_cell_with_condition(f"{total_cpu_alloc:.1f}", "CPU_Allocatable", None, 'nodes'),
                format_cell_with_condition(f"{total_mem_cap:.1f}", "Memory_Capacity", None, 'nodes'),
                format_cell_with_condition(f"{total_mem_alloc:.1f}", "Memory_Allocatable", None, 'nodes'),
                format_cell_with_condition(f"{cpu_efficiency:.1f}%", "CPU_Efficiency", None, 'nodes'),
                format_cell_with_condition(f"{mem_efficiency:.1f}%", "Memory_Efficiency", None, 'nodes')
            ]
            parts.append("<tr>" + "".join(row_cells) + "</tr>")
        parts.append("</table>")
        return parts

    def _generate_role_section(self, role: str, nodes: List[Dict]) -> List[str]:
        parts = [f"<h3>{html.escape(role.title())} Nodes ({len(nodes)})</h3>"]
        parts.append("<table border=1 cellpadding=4 cellspacing=0>")
        parts.append("<tr><th>Node Name</th><th>Instance Type</th><th>Zone</th>"
                    "<th>CPU Cap (m)</th><th>CPU Alloc (m)</th><th>Mem Cap (Mi)</th><th>Mem Alloc (Mi)</th>"
                    "<th>CPU Util %</th><th>Mem Util %</th></tr>")
        for node in sorted(nodes, key=lambda n: n['name']):
            cpu_util = (node['cpu_allocatable_m'] / node['cpu_capacity_m'] * 100) if node['cpu_capacity_m'] > 0 else 0
            mem_util = (node['memory_allocatable_mi'] / node['memory_capacity_mi'] * 100) if node['memory_capacity_mi'] > 0 else 0
            node_cells = [
                f"<td>{html.escape(node['name'])}</td>",
                f"<td>{html.escape(node['instance_type'])}</td>",
                f"<td>{html.escape(node['zone'])}</td>",
                format_cell_with_condition(f"{node['cpu_capacity_m']:.0f}", "CPU_Capacity_m", node, 'nodes'),
                format_cell_with_condition(f"{node['cpu_allocatable_m']:.0f}", "CPU_Allocatable_m", node, 'nodes'),
                format_cell_with_condition(f"{node['memory_capacity_mi']:.0f}", "Memory_Capacity_Mi", node, 'nodes'),
                format_cell_with_condition(f"{node['memory_allocatable_mi']:.0f}", "Memory_Allocatable_Mi", node, 'nodes'),
                format_cell_with_condition(f"{cpu_util:.1f}%", "CPU_Utilization", node, 'nodes'),
                format_cell_with_condition(f"{mem_util:.1f}%", "Memory_Utilization", node, 'nodes')
            ]
            parts.append("<tr>" + "".join(node_cells) + "</tr>")
        parts.append("</table>")
        return parts

    def _generate_cluster_totals(self, role_groups: Dict[str, List[Dict]]) -> List[str]:
        parts = ["<h2>Cluster Totals</h2>"]
        total_nodes = sum(len(nodes) for nodes in role_groups.values())
        total_cpu_cap = sum(sum(node['cpu_capacity_m'] for node in nodes) for nodes in role_groups.values()) / 1000
        total_cpu_alloc = sum(sum(node['cpu_allocatable_m'] for node in nodes) for nodes in role_groups.values()) / 1000
        total_mem_cap = sum(sum(node['memory_capacity_mi'] for node in nodes) for nodes in role_groups.values()) / 1024
        total_mem_alloc = sum(sum(node['memory_allocatable_mi'] for node in nodes) for nodes in role_groups.values()) / 1024
        overall_cpu_efficiency = (total_cpu_alloc / total_cpu_cap * 100) if total_cpu_cap > 0 else 0
        overall_mem_efficiency = (total_mem_alloc / total_mem_cap * 100) if total_mem_cap > 0 else 0
        parts.append("<ul>")
        parts.append(f"<li><strong>Total Nodes:</strong> {total_nodes}</li>")
        parts.append(f"<li><strong>Total CPU Capacity:</strong> {total_cpu_cap:.1f} cores</li>")
        parts.append(f"<li><strong>Total CPU Allocatable:</strong> {total_cpu_alloc:.1f} cores ({overall_cpu_efficiency:.1f}% efficiency)</li>")
        parts.append(f"<li><strong>Total Memory Capacity:</strong> {total_mem_cap:.1f} GiB</li>")
        parts.append(f"<li><strong>Total Memory Allocatable:</strong> {total_mem_alloc:.1f} GiB ({overall_mem_efficiency:.1f}% efficiency)</li>")
        parts.append("</ul>")
        return parts

    def _generate_empty_report(self, cluster: str, out_path: str) -> None:
        title = f"Nodes resource report: {html.escape(cluster)}"
        parts = [f"<h1>{title}</h1>", "<p>No node data available for this cluster.</p>"]
        html_doc = wrap_html_document(title, parts)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html_doc)
