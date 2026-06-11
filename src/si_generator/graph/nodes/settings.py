from __future__ import annotations

from ..state import GenerateSIState
from ...style_config import load_style_config


def load_settings_node(state: GenerateSIState) -> dict:
    request = state["request"]
    return {"style_config": load_style_config(request.style_config_path)}

