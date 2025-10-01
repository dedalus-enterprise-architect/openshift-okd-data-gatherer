from typing import Dict, Any
from .base import Rule, RuleResult, RuleType
from typing import Optional


class MissingCpuRequestRule(Rule):
    def __init__(self):
        super().__init__(name="missing_cpu_request", description="Missing value for CPU requests: ERROR_MISS")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '')
        return 'CPU_req' in column_name or ('cpu' in column_name.lower() and 'req' in column_name.lower())
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', '0', '0m']:
            return RuleResult(RuleType.ERROR_MISS, message="Missing CPU request value", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class MissingMemoryRequestRule(Rule):
    def __init__(self):
        super().__init__(name="missing_memory_request", description="Missing value for Memory requests: ERROR_MISS")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '')
        return 'Mem_req' in column_name or ('mem' in column_name.lower() and 'req' in column_name.lower())
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', '0', '0Mi', '0MiB']:
            return RuleResult(RuleType.ERROR_MISS, message="Missing Memory request value", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class MissingCpuLimitRule(Rule):
    def __init__(self):
        super().__init__(name="missing_cpu_limit", description="Missing value for CPU limits: WARNING_MISS")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '')
        return 'CPU_lim' in column_name or ('cpu' in column_name.lower() and 'lim' in column_name.lower())
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', '0', '0m']:
            return RuleResult(RuleType.WARNING_MISS, message="Missing CPU limit value", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class MissingMemoryLimitRule(Rule):
    def __init__(self):
        super().__init__(name="missing_memory_limit", description="Missing value for Memory limits: WARNING_MISS")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '')
        return 'Mem_lim' in column_name or ('mem' in column_name.lower() and 'lim' in column_name.lower())
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', '0', '0Mi', '0MiB']:
            return RuleResult(RuleType.WARNING_MISS, message="Missing Memory limit value", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class ImagePullPolicyAlwaysRule(Rule):
    def __init__(self):
        super().__init__(name="image_pull_policy_always", description="ImagePullPolicy set to Always: WARNING_MISCONF")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '').lower()
        return 'image' in column_name and 'pull' in column_name and 'policy' in column_name
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if cell_value == 'Always':
            return RuleResult(RuleType.WARNING_MISCONF, message="ImagePullPolicy set to Always", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class MissingReadinessProbeRule(Rule):
    def __init__(self):
        super().__init__(name="missing_readiness_probe", description="ReadinessProbe missing: ERROR_MISS")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '').lower()
        return 'readiness' in column_name and 'probe' in column_name
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', 'No', 'False', 'Missing', 'Not configured']:
            return RuleResult(RuleType.ERROR_MISS, message="ReadinessProbe missing", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class RequestLimitSkewRule(Rule):
    def __init__(self, threshold: float = 0.2):
        super().__init__(name="request_limit_skew", description=f"Request <= {int(threshold*100)}% of limit: WARNING_MISCONF")
        self.threshold = threshold
    def applies_to(self, context: Dict[str, Any]) -> bool:
        # Apply only once per resource type for CPU & Memory request columns (avoid duplicate on limit columns)
        col = context.get('column_name','')
        return col in ("CPU_req_m", "Mem_req_Mi")
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        row = context.get('row_data', {})
        try:
            if context.get('column_name') == 'CPU_req_m':
                req = int(row.get('CPU_req_m') or 0)
                lim = int(row.get('CPU_lim_m') or 0)
            else:
                req = int(row.get('Mem_req_Mi') or 0)
                lim = int(row.get('Mem_lim_Mi') or 0)
            if lim > 0 and req > 0 and req/lim <= self.threshold:
                return RuleResult(RuleType.WARNING_MISCONF, message=f"Request <= {int(self.threshold*100)}% of limit", matched_rule=self.name)
        except Exception:
            pass
        return RuleResult(RuleType.NONE)


class LimitExceedsSmallestNodeRule(Rule):
    def __init__(self, smallest_cpu_m: Optional[int] = None, smallest_mem_mi: Optional[int] = None):
        super().__init__(name="limit_exceeds_smallest_node", description="Limit >= smallest node size: ERROR_MISCONF")
        self.smallest_cpu_m = smallest_cpu_m
        self.smallest_mem_mi = smallest_mem_mi
    def applies_to(self, context: Dict[str, Any]) -> bool:
        return context.get('column_name') in ("CPU_lim_m", "Mem_lim_Mi")
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        val = context.get('cell_value')
        col = context.get('column_name')
        try:
            ival = int(val) if val not in (None, '', '-', 'N/A') else 0
        except Exception:
            return RuleResult(RuleType.NONE)
        if col == 'CPU_lim_m' and self.smallest_cpu_m and ival >= self.smallest_cpu_m:
            return RuleResult(RuleType.ERROR_MISCONF, message="CPU limit >= smallest node CPUs", matched_rule=self.name)
        if col == 'Mem_lim_Mi' and self.smallest_mem_mi and ival >= self.smallest_mem_mi:
            return RuleResult(RuleType.ERROR_MISCONF, message="Memory limit >= smallest node Memory", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


def register_official_rules(registry) -> None:
    # Determine smallest node resources if available via injected context later (lazy approach: rules using dynamic thresholds may be re-created externally)
    for rule in [
        MissingCpuRequestRule(),
        MissingMemoryRequestRule(),
        MissingCpuLimitRule(),
        MissingMemoryLimitRule(),
        ImagePullPolicyAlwaysRule(),
        MissingReadinessProbeRule(),
        RequestLimitSkewRule(),
        LimitExceedsSmallestNodeRule(),
    ]:
        registry.register(rule)
