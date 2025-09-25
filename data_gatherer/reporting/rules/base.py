from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional


class RuleType(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    NONE = "none"


@dataclass
class RuleResult:
    rule_type: RuleType
    message: Optional[str] = None
    matched_rule: Optional[str] = None

    @property
    def css_class(self) -> str:
        if self.rule_type == RuleType.ERROR:
            return "error-cell"
        elif self.rule_type == RuleType.WARNING:
            return "warning-cell"
        else:
            return ""

    def __bool__(self) -> bool:
        return self.rule_type in (RuleType.ERROR, RuleType.WARNING, RuleType.INFO)


class Rule(ABC):
    def __init__(self, name: str, description: str, enabled: bool = True):
        self.name = name
        self.description = description
        self.enabled = enabled

    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> RuleResult:  # pragma: no cover
        pass

    @abstractmethod
    def applies_to(self, context: Dict[str, Any]) -> bool:  # pragma: no cover
        pass
