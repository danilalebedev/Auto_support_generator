from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..adapters.legacy_compound import legacy_compounds_to_domain
from ..domain.types import GenerationConfig, JournalProfile, RuntimeConfig, SIState, SpectraProcessingConfig
from ..models import Compound as LegacyCompound


def default_spectra_config() -> SpectraProcessingConfig:
    return {
        "extract_nmr": True,
        "insert_spectra_as": "png",
        "target_signal_height_fraction": 0.80,
        "peak_picking": "normal",
        "keep_intermediate_reports": True,
    }


def default_generation_config() -> GenerationConfig:
    return {
        "generate_loadings": False,
        "include_ir": True,
        "include_elemental_analysis": False,
        "include_references": False,
        "include_xrd": False,
        "validate_only": False,
        "patch_existing_support": False,
    }


def default_journal_profile() -> JournalProfile:
    return {
        "id": "default",
        "name": "Default SI profile",
        "section_order": ["compound_descriptions", "spectra_appendix"],
        "use_subscripts_in_formulae": True,
        "use_superscript_isotopes": True,
        "use_italic_j": True,
    }


def default_runtime_config() -> RuntimeConfig:
    return {"gui": False, "debug": False, "dry_run": False}


def make_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return now.strftime("%Y%m%dT%H%M%S")


def make_initial_state(
    *,
    legacy_compounds: list[LegacyCompound] | None = None,
    input_paths: dict[str, str] | None = None,
    output_paths: dict[str, str] | None = None,
    spectra_config: SpectraProcessingConfig | None = None,
    generation_config: GenerationConfig | None = None,
    journal_profile: JournalProfile | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> SIState:
    compounds, order = legacy_compounds_to_domain(legacy_compounds or [])
    return {
        "run_id": make_run_id(),
        "compounds": compounds,
        "order": order,
        "spectra_config": spectra_config or default_spectra_config(),
        "generation_config": generation_config or default_generation_config(),
        "journal_profile": journal_profile or default_journal_profile(),
        "runtime_config": runtime_config or default_runtime_config(),
        "input_paths": _stringify_paths(input_paths or {}),
        "output_paths": _stringify_paths(output_paths or {}),
        "artifacts": {},
        "issues": [],
        "logs": [],
        "manifest": {},
    }


def _stringify_paths(paths: dict[str, str]) -> dict[str, str]:
    return {key: str(Path(value)) if value else "" for key, value in paths.items()}

