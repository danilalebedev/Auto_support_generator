from __future__ import annotations

from ..state import GenerateSIState
from ...domain.generation_config import build_generation_config
from ...domain.journal_profile import load_journal_profile
from ...domain.references import load_reference_store
from ...domain.spectra_config import build_spectra_config
from ...style_config import load_style_config


def load_settings_node(state: GenerateSIState) -> dict:
    request = state["request"]
    style_config = load_style_config(request.style_config_path)
    return {
        "style_config": style_config,
        "journal_profile": load_journal_profile(request.journal_profile),
        "reference_store": load_reference_store(request.references_path),
        "spectra_config": build_spectra_config(
            extract_nmr=not request.no_extract_nmr,
            insert_spectra_as=request.insert_spectra_as,
            mnova_executable_path=str(request.mnova_exe) if request.mnova_exe else None,
        ),
        "generation_config": build_generation_config(
            style_config=style_config,
            generate_loadings=request.generate_loadings,
            has_references=bool(request.references_path),
            check_support=not request.no_check_support,
        ),
        "runtime_config": {
            "gui": False,
            "debug": False,
            "dry_run": False,
        },
    }

