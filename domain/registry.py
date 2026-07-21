"""
domain/registry.py — Service registry for dependency injection.
Use cases resolve dependencies through this registry instead of importing utils/ directly.
"""
from typing import Dict, Any

_registry: Dict[str, Any] = {}


def register(name: str, implementation: Any) -> None:
    _registry[name] = implementation


def resolve(name: str) -> Any:
    if name not in _registry:
        raise KeyError(f"Service '{name}' not registered. Call register() first.")
    return _registry[name]


def register_defaults() -> None:
    """Register all default service implementations. Call once at startup."""
    import pandas as pd
    from utils.folio_parser import parse_folios, calculate_suggested_range
    from utils.folio_engine import mapper_from_state
    from utils.analyzers import analizar_folios, analizar_topica, analizar_cronica, analizar_coverage
    from utils.hierarchy_builder import build_11_level_path, RomanToSigloArabic
    register("pandas", pd)
    register("parse_folios", parse_folios)
    register("calculate_suggested_range", calculate_suggested_range)
    register("mapper_from_state", mapper_from_state)
    register("analizar_folios", analizar_folios)
    register("analizar_topica", analizar_topica)
    register("analizar_cronica", analizar_cronica)
    register("analizar_coverage", analizar_coverage)
    register("build_11_level_path", build_11_level_path)
    register("RomanToSigloArabic", RomanToSigloArabic)

