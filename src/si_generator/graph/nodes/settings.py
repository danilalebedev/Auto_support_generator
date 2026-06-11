from __future__ import annotations

from ..state import GenerateSIState
from ...domain.references import load_reference_store
from .spectra import DEFAULT_PEAK_PICKING, DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION
from ...render.journal_profile import load_journal_profile
from ...style_config import config_get, load_style_config


def load_settings_node(state: GenerateSIState) -> dict:
    request = state["request"]
    style_config = load_style_config(request.style_config_path)
    return {
        "style_config": style_config,
        "journal_profile": load_journal_profile(request.journal_profile),
        "reference_store": load_reference_store(request.references_path),
        "spectra_config": {
            "extract_nmr": not request.no_extract_nmr,
            "insert_spectra_as": request.insert_spectra_as,
            "target_signal_height_fraction": DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION,
            "solvent_suppression": True,
            "ignore_regions_ppm": {},
            "peak_picking": DEFAULT_PEAK_PICKING,
            "keep_intermediate_reports": True,
            **({"mnova_executable_path": str(request.mnova_exe)} if request.mnova_exe else {}),
        },
        "generation_config": _generation_config(request, style_config),
        "runtime_config": {
            "gui": False,
            "debug": False,
            "dry_run": False,
        },
    }


def _generation_config(request, style_config: dict) -> dict:
    config = {
        "generate_loadings": request.generate_loadings,
        "include_ir": True,
        "include_elemental_analysis": True,
        "calculate_elemental_analysis": False,
        "include_references": bool(request.references_path),
        "include_xrd": False,
        "check_support": not request.no_check_support,
        "validate_only": False,
        "patch_existing_support": False,
    }
    generation_style = config_get(style_config, "generation", {})
    if isinstance(generation_style, dict):
        for key in (
            "include_ir",
            "include_elemental_analysis",
            "calculate_elemental_analysis",
            "include_references",
            "include_xrd",
        ):
            if key in generation_style:
                config[key] = bool(generation_style[key])
    if not request.references_path:
        config["include_references"] = False
    return config

