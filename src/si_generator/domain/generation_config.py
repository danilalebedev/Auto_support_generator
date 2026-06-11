from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .types import GenerationConfig


GENERATION_STYLE_KEYS = (
    "include_ir",
    "include_elemental_analysis",
    "calculate_elemental_analysis",
    "include_references",
    "include_xrd",
)


def build_generation_config(
    *,
    style_config: Mapping[str, Any] | None = None,
    generate_loadings: bool = False,
    has_references: bool = False,
    check_support: bool = True,
) -> GenerationConfig:
    config: GenerationConfig = {
        "generate_loadings": generate_loadings,
        "include_ir": True,
        "include_elemental_analysis": True,
        "calculate_elemental_analysis": False,
        "include_references": has_references,
        "include_xrd": False,
        "check_support": check_support,
        "validate_only": False,
        "patch_existing_support": False,
    }
    generation_style = _mapping_get(style_config or {}, "generation", {})
    if isinstance(generation_style, Mapping):
        for key in GENERATION_STYLE_KEYS:
            if key in generation_style:
                config[key] = bool(generation_style[key])
    if not has_references:
        config["include_references"] = False
    return config


def _mapping_get(mapping: Mapping[str, Any], key: str, default: Any = None) -> Any:
    return mapping.get(key, default) if isinstance(mapping, Mapping) else default
