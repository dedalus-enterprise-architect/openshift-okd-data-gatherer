from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Type


class ReportGenerator(ABC):
    """Abstract base for report generators.

    Implementations should write their output to the provided out_path.
    """

    # A short unique type name (e.g. 'html', 'summary-json')
    type_name: str
    # Default file extension including dot (e.g. '.html', '.json')
    file_extension: str
    # Default filename prefix (before timestamp) for auto output naming
    filename_prefix: str = 'report-'

    @abstractmethod
    def generate(self, db, cluster: str, out_path: str) -> None:  # pragma: no cover - interface
        pass


_registry: Dict[str, Type[ReportGenerator]] = {}


def register(generator_cls: Type[ReportGenerator]):
    name = getattr(generator_cls, 'type_name', None)
    if not name:
        raise ValueError('ReportGenerator subclass must define type_name')
    _registry[name] = generator_cls
    return generator_cls


def get_report_types():
    return sorted(_registry.keys())


def get_generator(type_name: str) -> ReportGenerator:
    cls = _registry.get(type_name)
    if not cls:
        raise ValueError(f'Unknown report type: {type_name}. Available: {", ".join(get_report_types())}')
    return cls()
