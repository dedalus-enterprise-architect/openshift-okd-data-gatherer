"""Common utilities for report generation.

This module provides shared functionality used across multiple report generators,
including resource parsing, pod spec extraction, and HTML generation utilities.
"""
from __future__ import annotations
import html
from typing import Optional, Dict, Any, List
from .rules import RulesEngine, RuleRegistry, register_official_rules


# Common workload kinds for container-based reports
CONTAINER_WORKLOAD_KINDS = {
    "Deployment", "StatefulSet", "DaemonSet", "DeploymentConfig", "Job", "CronJob"
}


# Global rules engine instance
_rules_registry = None
_rules_engine = None


def get_rules_engine() -> RulesEngine:
    """Get the global rules engine instance."""
    global _rules_registry, _rules_engine

    if _rules_engine is None:
        _rules_registry = RuleRegistry()
        register_official_rules(_rules_registry)
        _rules_engine = RulesEngine(_rules_registry)

    return _rules_engine


def cpu_to_milli(val: Optional[str]) -> Optional[int]:
    """Convert CPU resource string to millicores."""
    if not val:
        return None
    try:
        if val.endswith('m'):
            return int(val[:-1])
        # plain integer/float cores
        return int(float(val) * 1000)
    except Exception:
        return None


def mem_to_mi(val: Optional[str]) -> Optional[int]:
    """Convert memory resource string to MiB."""
    if not val:
        return None
    try:
        lower = val.lower()
        if lower.endswith('ki'):
            return int(int(lower[:-2]) / 1024)
        if lower.endswith('mi'):
            return int(lower[:-2])
        if lower.endswith('gi'):
            return int(lower[:-2]) * 1024
        if lower.endswith('ti'):
            return int(lower[:-2]) * 1024 * 1024
        num = int(lower)
        return num
    except Exception:
        return None


def extract_pod_spec(kind: str, manifest: dict) -> Optional[dict]:
    spec = manifest.get('spec') or {}
    if kind in {"Deployment", "StatefulSet", "DaemonSet", "DeploymentConfig"}:
        return (spec.get('template') or {}).get('spec')
    if kind == 'Job':
        return (spec.get('template') or {}).get('spec')
    if kind == 'CronJob':
        return (((spec.get('jobTemplate') or {}).get('spec') or {}).get('template') or {}).get('spec')
    return None


def get_replicas_for_workload(kind: str, manifest: dict) -> Optional[int]:
    spec = manifest.get('spec') or {}
    if kind in {"Deployment", "StatefulSet", "DeploymentConfig"}:
        return spec.get('replicas', 1)
    if kind == 'Job':
        return spec.get('parallelism', spec.get('completions', 1))
    if kind == 'CronJob':
        job_spec = (spec.get('jobTemplate') or {}).get('spec') or {}
        return job_spec.get('parallelism', job_spec.get('completions', 1))
    if kind == 'DaemonSet':
        return None
    return None


def build_legend_html(sections: List[Dict[str, Any]]) -> str:
    parts = ['<div class="legend">', '<h3>Legend</h3>']
    for section in sections:
        parts.append('<div class="legend-section">')
        parts.append(f'<h4>{html.escape(section["title"])}</h4>')
        parts.append('<ul>')
        for item in section["items"]:
            if isinstance(item, dict):
                if 'class' in item and 'description' in item:
                    parts.append(f'<li><span class="legend-box {item["class"]}"></span> <strong>{item["description"]}</strong></li>')
                elif 'description' in item:
                    parts.append(f'<li>{item["description"]}</li>')
                else:
                    parts.append(f'<li>{html.escape(str(item))}</li>')
            else:
                parts.append(f'<li>{item}</li>')
        parts.append('</ul>')
        parts.append('</div>')
    parts.append('</div>')
    return '\n'.join(parts)


def get_common_legend_sections() -> List[Dict[str, Any]]:
    return [
        {"title": "Container Types", "items": ["<strong>main</strong>: Application containers", "<strong>init</strong>: Initialization containers"]},
        {"title": "Units", "items": ["<strong>CPU</strong>: millicores (1000m = 1 core)", "<strong>Memory</strong>: MiB (1024 MiB = 1 GiB)"]},
    ]


def get_base_css_styles() -> str:
    return """
body { font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 20px; color: #212529; line-height: 1.5; }
h1, h2, h3, h4, h5, h6 { color: #343a40; margin-top: 0; margin-bottom: 1rem; }
table { border-collapse: collapse; margin-bottom: 16px; width: 100%; font-size: 13px; }
th { background: #343a40; color: #ffffff; font-weight: 600; text-align: left; border: 1px solid #dee2e6; padding: 8px; vertical-align: top; }
td { border: 1px solid #dee2e6; padding: 8px; vertical-align: top; color: #343a40; }
table tr:nth-child(even) { background-color: #f8f9fa; }
table tr:hover { background-color: #e3f2fd !important; transition: background-color 0.2s ease; }
.legend { background: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; margin: 15px 0; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 11px; }
.legend h3 { margin: 0 0 10px 0; color: #343a40; font-size: 12px; font-weight: 600; }
.legend h4 { margin: 10px 0 5px 0; color: #495057; font-size: 11px; font-weight: 500; }
.legend-section { margin-bottom: 20px; }
.legend ul { margin: 8px 0; padding-left: 24px; }
.legend li { margin: 5px 0; color: #6c757d; }
.legend-box { display: inline-block; width: 15px; height: 15px; border: 1px solid #adb5bd; margin-right: 8px; vertical-align: middle; }
.warning-cell { background-color: #fff3cd !important; border-color: #ffeaa7 !important; }
.error-cell { background-color: #f8d7da !important; border-color: #f5c6cb !important; }
""".strip()


def is_warning_condition(value: str, column_name: str, row_data: Optional[Dict[str, Any]] = None) -> bool:
    rules_engine = get_rules_engine()
    context = {
        'cell_value': value,
        'column_name': column_name,
        'row_data': row_data or {},
        'report_type': 'generic'
    }
    result = rules_engine.evaluate_cell(context)
    return result.rule_type.value == 'warning'


def is_error_condition(value: str, column_name: str, row_data: Optional[Dict[str, Any]] = None) -> bool:
    rules_engine = get_rules_engine()
    context = {
        'cell_value': value,
        'column_name': column_name,
        'row_data': row_data or {},
        'report_type': 'generic'
    }
    result = rules_engine.evaluate_cell(context)
    return result.rule_type.value == 'error'


def format_cell_with_condition(value: str, column_name: str, row_data: Optional[Dict[str, Any]] = None, report_type: str = 'generic') -> str:
    escaped_value = html.escape(str(value))
    rules_engine = get_rules_engine()
    context = {
        'cell_value': value,
        'column_name': column_name,
        'row_data': row_data or {},
        'report_type': report_type
    }
    result = rules_engine.evaluate_cell(context)
    css_class = result.css_class
    if css_class:
        return f'<td class="{css_class}">{escaped_value}</td>'
    else:
        return f'<td>{escaped_value}</td>'


def wrap_html_document(title: str, content_parts: List[str], additional_css: str = "") -> str:
    base_css = get_base_css_styles()
    full_css = base_css + ("\n" + additional_css if additional_css else "")
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)}</title>
  <style>
{full_css}
  </style>
</head>
<body>
{chr(10).join(content_parts)}
</body>
</html>"""
