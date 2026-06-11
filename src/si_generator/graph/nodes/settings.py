from __future__ import annotations

from ..state import GenerateSIState
from ...domain.references import load_reference_store
from ...render.journal_profile import load_journal_profile
from ...style_config import load_style_config


def load_settings_node(state: GenerateSIState) -> dict:
    request = state["request"]
    return {
        "style_config": load_style_config(request.style_config_path),
        "journal_profile": load_journal_profile(request.journal_profile),
        "reference_store": load_reference_store(request.references_path),
    }

