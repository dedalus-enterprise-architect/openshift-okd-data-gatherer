from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional


class RuleType(Enum):
    # Missing configuration (background highlighting)
    ERROR_MISS = "error_miss"
    WARNING_MISS = "warning_miss"
    # Misconfiguration (text emphasis)
    ERROR_MISCONF = "error_misconf"
    WARNING_MISCONF = "warning_misconf"
    INFO = "info"
    NONE = "none"


@dataclass
class RuleResult:
    rule_type: RuleType
    message: Optional[str] = None
    matched_rule: Optional[str] = None

    @property
    def css_class(self) -> str:
        mapping = {
            RuleType.ERROR_MISS: "error-miss-cell",
            RuleType.WARNING_MISS: "warning-miss-cell",
            RuleType.ERROR_MISCONF: "error-misconf-cell",
            RuleType.WARNING_MISCONF: "warning-misconf-cell",
        }
        return mapping.get(self.rule_type, "")

    def __bool__(self) -> bool:
        return self.rule_type not in (RuleType.NONE,)


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
