from __future__ import annotations

from .types import GenerationConfig


def build_generation_config(
    *,
    generate_loadings: bool = False,
    calculate_elemental_analysis: bool = False,
    has_references: bool = False,
    check_support: bool = True,
) -> GenerationConfig:
    config: GenerationConfig = {
        "generate_loadings": generate_loadings,
        "include_ir": True,
        "include_elemental_analysis": True,
        "calculate_elemental_analysis": calculate_elemental_analysis,
        "include_references": has_references,
        "check_support": check_support,
        "validate_only": False,
        "patch_existing_support": False,
    }
    if not has_references:
        config["include_references"] = False
    return config
