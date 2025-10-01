from __future__ import annotations
import html
from typing import List, Dict
from .base import ReportGenerator, register
from ..persistence.db import WorkloadDB
from ..persistence.workload_queries import WorkloadQueries
from .common import (
	cpu_to_milli, mem_to_mi,
	build_legend_html, wrap_html_document,
	CONTAINER_WORKLOAD_KINDS, extract_pod_spec, get_replicas_for_workload
)


@register
class ClusterCapacityReport(ReportGenerator):

	type_name = 'cluster-capacity'
	file_extension = '.html'
	filename_prefix = 'cluster-capacity-'

	def generate(self, db: WorkloadDB, cluster: str, out_path: str) -> None:  # noqa: D401
		wq = WorkloadQueries(db)

		rows = wq.list_for_kinds(cluster, list(CONTAINER_WORKLOAD_KINDS))

		ns_totals: Dict[str, Dict[str, int]] = {}
		for rec in rows:
			namespace = rec['namespace'] or '<cluster-scoped>'
			manifest = rec['manifest']
			kind = rec['kind']
			pod_spec = extract_pod_spec(kind, manifest)
			if not pod_spec:
				continue
			replicas = get_replicas_for_workload(kind, manifest) or 1
			ns_totals.setdefault(namespace, {'cpu': 0, 'mem': 0, 'cpu_lim': 0, 'mem_lim': 0})
			for cdef in pod_spec.get('containers', []):
				res = cdef.get('resources', {})
				req = res.get('requests', {}) or {}
				lim = res.get('limits', {}) or {}
				cpu_req = cpu_to_milli(req.get('cpu')) or 0
				mem_req = mem_to_mi(req.get('memory')) or 0
				cpu_lim = cpu_to_milli(lim.get('cpu')) or 0
				mem_lim = mem_to_mi(lim.get('memory')) or 0
				if cpu_req:
					ns_totals[namespace]['cpu'] += cpu_req * replicas
				if mem_req:
					ns_totals[namespace]['mem'] += mem_req * replicas
				if cpu_lim:
					ns_totals[namespace]['cpu_lim'] += cpu_lim * replicas
				if mem_lim:
					ns_totals[namespace]['mem_lim'] += mem_lim * replicas

		cur = db._conn.cursor()
		node_rows = cur.execute(
			"""SELECT cpu_allocatable, memory_allocatable, cpu_capacity, memory_capacity
			   FROM node_capacity
			   WHERE cluster=? AND deleted=0 AND node_role='worker'""",
			(cluster,)
		).fetchall()
		total_cpu_alloc = total_mem_alloc = 0
		for cpu_alloc, mem_alloc, cpu_cap, mem_cap in node_rows:
			total_cpu_alloc += (cpu_to_milli(cpu_alloc) or cpu_to_milli(cpu_cap) or 0)
			total_mem_alloc += (mem_to_mi(mem_alloc) or mem_to_mi(mem_cap) or 0)

		table = [
			'<table border=1 cellpadding=4 cellspacing=0>',
			'<tr><th>Namespace</th><th>CPU Requests (m)</th><th>Memory Requests (Mi)</th>'
			'<th>CPU Limits (m)</th><th>Memory Limits (Mi)</th>'
			'<th>% CPU allocated on Cluster</th><th>% Memory allocated on Cluster</th></tr>'
		]
		if not ns_totals:
			table.append('<tr><td colspan="6" style="text-align:center; font-style:italic;">No workloads found</td></tr>')
		elif total_cpu_alloc == 0 and total_mem_alloc == 0:
			table.append('<tr><td colspan="6" style="text-align:center; font-style:italic;">No worker node capacity data</td></tr>')
		else:
			for ns, totals in sorted(ns_totals.items(), key=lambda x: (
				(x[1]['cpu'] / total_cpu_alloc * 100 if total_cpu_alloc else 0) +
				(x[1]['mem'] / total_mem_alloc * 100 if total_mem_alloc else 0)
			), reverse=True):
				cpu = totals['cpu']
				mem = totals['mem']
				cpu_lim_ns = totals['cpu_lim']
				mem_lim_ns = totals['mem_lim']
				cpu_pct_str = f"{cpu / total_cpu_alloc * 100:.1f}%" if total_cpu_alloc else 'N/A'
				mem_pct_str = f"{mem / total_mem_alloc * 100:.1f}%" if total_mem_alloc else 'N/A'
				table.append(
					f'<tr><td>{html.escape(ns)}</td><td>{cpu:,}</td><td>{mem:,}</td>'
					f'<td>{cpu_lim_ns:,}</td><td>{mem_lim_ns:,}</td>'
					f'<td>{cpu_pct_str}</td><td>{mem_pct_str}</td></tr>'
				)
			# Totals row summarizing all namespaces
			if ns_totals:
				all_req_cpu = sum(v['cpu'] for v in ns_totals.values())
				all_req_mem = sum(v['mem'] for v in ns_totals.values())
				all_lim_cpu = sum(v['cpu_lim'] for v in ns_totals.values())
				all_lim_mem = sum(v['mem_lim'] for v in ns_totals.values())
				cpu_pct_total = f"{all_req_cpu / total_cpu_alloc * 100:.1f}%" if total_cpu_alloc else 'N/A'
				mem_pct_total = f"{all_req_mem / total_mem_alloc * 100:.1f}%" if total_mem_alloc else 'N/A'
				table.append(
					'<tr class="totals-row-all">'
					f'<td><strong>Totals</strong></td><td><strong>{all_req_cpu:,}</strong></td>'
					f'<td><strong>{all_req_mem:,}</strong></td>'
					f'<td><strong>{all_lim_cpu:,}</strong></td><td><strong>{all_lim_mem:,}</strong></td>'
					f'<td><strong>{cpu_pct_total}</strong></td><td><strong>{mem_pct_total}</strong></td>'
					'</tr>'
				)
		table.append('</table>')

		total_req_cpu = sum(v['cpu'] for v in ns_totals.values())
		total_req_mem = sum(v['mem'] for v in ns_totals.values())
		total_lim_cpu = sum(v['cpu_lim'] for v in ns_totals.values())
		total_lim_mem = sum(v['mem_lim'] for v in ns_totals.values())

		def _pct(v: int, d: int) -> str:
			return 'N/A' if d <= 0 else f"{v / d * 100:.1f}%"

		totals_table: List[str] = [
			'<table border=1 cellpadding=4 cellspacing=0>',
			'<tr><th>Scope</th><th>CPU (m)</th><th>CPU % Allocatable</th><th>Memory (Mi)</th><th>Memory % Allocatable</th></tr>'
		]
		# Baseline cluster worker allocatable (always 100% when >0)
		alloc_cpu_pct = '100.0%' if total_cpu_alloc > 0 else 'N/A'
		alloc_mem_pct = '100.0%' if total_mem_alloc > 0 else 'N/A'
		totals_table.append(
			'<tr>'
			f'<td>Total resources allocatable on Worker nodes</td><td>{total_cpu_alloc:,}</td><td>{alloc_cpu_pct}</td>'
			f'<td>{total_mem_alloc:,}</td><td>{alloc_mem_pct}</td></tr>'
		)
		totals_table.append(
			'<tr>'
			f'<td>Main Containers Requests</td><td>{total_req_cpu:,}</td><td>{_pct(total_req_cpu, total_cpu_alloc)}</td>'
			f'<td>{total_req_mem:,}</td><td>{_pct(total_req_mem, total_mem_alloc)}</td></tr>'
		)
		# Free allocatable (clamped to 0 for overcommit)
		free_cpu = max(0, total_cpu_alloc - total_req_cpu)
		free_mem = max(0, total_mem_alloc - total_req_mem)
		totals_table.append(
			'<tr>'
			f'<td>Free resources (Allocatable - Requests)</td><td>{free_cpu:,}</td><td>{_pct(free_cpu, total_cpu_alloc)}</td>'
			f'<td>{free_mem:,}</td><td>{_pct(free_mem, total_mem_alloc)}</td></tr>'
		)
		totals_table.append(
			'<tr>'
			f'<td>Main Containers Limits</td><td>{total_lim_cpu:,}</td><td>{_pct(total_lim_cpu, total_cpu_alloc)}</td>'
			f'<td>{total_lim_mem:,}</td><td>{_pct(total_lim_mem, total_mem_alloc)}</td></tr>'
		)
		totals_table.append('</table>')

		legend_sections = [
			{
				'title': 'Columns',
				'items': [
					"Namespace: OpenShift projects",
					'CPU/Memory Requests: Sum of all main containers requests x replica number',
					'CPU/Memory Limits: Sum of all main containers limits x replica number',
					'% CPU/Memory allocated on Cluster: Percentage of Allocatable resources consumed',
					'Totals: Aggregated namespace requests & limits (percent uses requests)',
					'Container Requests vs Allocatable resources on Worker Nodes: Allocatable baseline, requests, free allocatable, limits'
				]
			}
		]
		legend_html = build_legend_html(legend_sections)
		html_out = wrap_html_document(
			f'Cluster Capacity Report: {html.escape(cluster)}',
			[legend_html, '<h2>Requests and Limits per namespace</h2>', *table,
			 '<h2>Container Requests vs Allocatable resources on Worker Nodes</h2>', *totals_table]
		)
		with open(out_path, 'w', encoding='utf-8') as f:
			f.write(html_out)

