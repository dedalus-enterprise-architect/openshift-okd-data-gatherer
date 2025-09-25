from typing import Dict, Any, Optional
from .base import RuleResult, RuleType
from .registry import RuleRegistry


class RulesEngine:
    def __init__(self, registry: Optional[RuleRegistry] = None):
        self.registry = registry or RuleRegistry()
        self._cache_enabled = True
        self._evaluation_cache: Dict[str, RuleResult] = {}

    def evaluate_cell(self, context: Dict[str, Any]) -> RuleResult:
        cache_key = None
        if self._cache_enabled:
            cache_key = self._generate_cache_key(context)
            if cache_key in self._evaluation_cache:
                return self._evaluation_cache[cache_key]
        applicable_rules = self.registry.get_applicable_rules(context)
        if not applicable_rules:
            result = RuleResult(RuleType.NONE)
            if cache_key:
                self._evaluation_cache[cache_key] = result
            return result
        highest_result = RuleResult(RuleType.NONE)
        for rule in applicable_rules:
            try:
                rule_result = rule.evaluate(context)
                if rule_result and self._is_higher_severity(rule_result.rule_type, highest_result.rule_type):
                    highest_result = rule_result
                    if rule_result.rule_type == RuleType.ERROR:
                        break
            except Exception as e:  # pragma: no cover
                print(f"Warning: Rule '{rule.name}' failed to evaluate: {e}")
                continue
        if cache_key:
            self._evaluation_cache[cache_key] = highest_result
        return highest_result

    def clear_cache(self) -> None:
        self._evaluation_cache.clear()

    def enable_cache(self, enabled: bool = True) -> None:
        self._cache_enabled = enabled
        if not enabled:
            self.clear_cache()

    def _generate_cache_key(self, context: Dict[str, Any]) -> str:
        row_data = context.get('row_data', {})
        column_name = context.get('column_name', '')
        cell_value = context.get('cell_value', '')
        report_type = context.get('report_type', '')
        key_parts = [
            report_type,
            column_name,
            str(cell_value),
            str(hash(frozenset(row_data.items()) if isinstance(row_data, dict) else str(row_data)))
        ]
        return '|'.join(key_parts)

    def _is_higher_severity(self, new_type: RuleType, current_type: RuleType) -> bool:
        severity_order = {RuleType.NONE: 0, RuleType.INFO: 1, RuleType.WARNING: 2, RuleType.ERROR: 3}
        return severity_order[new_type] > severity_order[current_type]
