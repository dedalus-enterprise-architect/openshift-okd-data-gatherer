from typing import List, Dict, Any
from .base import Rule


class RuleRegistry:
    """Registry for rules providing filtering by applicability."""

    def __init__(self):
        self._rules: List[Rule] = []

    def register(self, rule: Rule):
        self._rules.append(rule)

    def get_rules(self) -> List[Rule]:  # pragma: no cover - trivial
        return list(self._rules)

    def get_applicable_rules(self, context: Dict[str, Any]) -> List[Rule]:
        return [r for r in self._rules if r.enabled and r.applies_to(context)]

    # Extended API for tests / management
    def get_rule(self, name: str) -> Rule:
        for r in self._rules:
            if r.name == name:
                return r
        raise KeyError(name)

    def unregister(self, name: str) -> bool:
        for i, r in enumerate(self._rules):
            if r.name == name:
                self._rules.pop(i)
                return True
        return False

    def enable_rule(self, name: str) -> bool:
        try:
            r = self.get_rule(name)
            r.enabled = True
            return True
        except KeyError:
            return False

    def disable_rule(self, name: str) -> bool:
        try:
            r = self.get_rule(name)
            r.enabled = False
            return True
        except KeyError:
            return False
