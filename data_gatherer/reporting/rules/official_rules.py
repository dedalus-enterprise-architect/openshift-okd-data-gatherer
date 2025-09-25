from typing import Dict, Any
from .base import Rule, RuleResult, RuleType


class MissingCpuRequestRule(Rule):
    def __init__(self):
        super().__init__(name="missing_cpu_request", description="Missing value for CPU requests: ERROR")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '')
        return 'CPU_req' in column_name or ('cpu' in column_name.lower() and 'req' in column_name.lower())
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', '0', '0m']:
            return RuleResult(RuleType.ERROR, message="Missing CPU request value", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class MissingMemoryRequestRule(Rule):
    def __init__(self):
        super().__init__(name="missing_memory_request", description="Missing value for Memory requests: ERROR")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '')
        return 'Mem_req' in column_name or ('mem' in column_name.lower() and 'req' in column_name.lower())
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', '0', '0Mi', '0MiB']:
            return RuleResult(RuleType.ERROR, message="Missing Memory request value", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class MissingCpuLimitRule(Rule):
    def __init__(self):
        super().__init__(name="missing_cpu_limit", description="Missing value for CPU limits: WARNING")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '')
        return 'CPU_lim' in column_name or ('cpu' in column_name.lower() and 'lim' in column_name.lower())
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', '0', '0m']:
            return RuleResult(RuleType.WARNING, message="Missing CPU limit value", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class MissingMemoryLimitRule(Rule):
    def __init__(self):
        super().__init__(name="missing_memory_limit", description="Missing value for Memory limits: WARNING")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '')
        return 'Mem_lim' in column_name or ('mem' in column_name.lower() and 'lim' in column_name.lower())
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', '0', '0Mi', '0MiB']:
            return RuleResult(RuleType.WARNING, message="Missing Memory limit value", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class ImagePullPolicyAlwaysRule(Rule):
    def __init__(self):
        super().__init__(name="image_pull_policy_always", description="ImagePullPolicy set to Always: WARNING")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '').lower()
        return 'image' in column_name and 'pull' in column_name and 'policy' in column_name
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if cell_value == 'Always':
            return RuleResult(RuleType.WARNING, message="ImagePullPolicy set to Always", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


class MissingReadinessProbeRule(Rule):
    def __init__(self):
        super().__init__(name="missing_readiness_probe", description="ReadinessProbe missing: ERROR")
    def applies_to(self, context: Dict[str, Any]) -> bool:
        column_name = context.get('column_name', '').lower()
        return 'readiness' in column_name and 'probe' in column_name
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        cell_value = context.get('cell_value', '')
        if not cell_value or cell_value in ['-', 'N/A', 'None', 'No', 'False', 'Missing']:
            return RuleResult(RuleType.ERROR, message="ReadinessProbe missing", matched_rule=self.name)
        return RuleResult(RuleType.NONE)


def register_official_rules(registry) -> None:
    for rule in [
        MissingCpuRequestRule(),
        MissingMemoryRequestRule(),
        MissingCpuLimitRule(),
        MissingMemoryLimitRule(),
        ImagePullPolicyAlwaysRule(),
        MissingReadinessProbeRule(),
    ]:
        registry.register(rule)
