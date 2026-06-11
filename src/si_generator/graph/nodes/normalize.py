from __future__ import annotations

from ..compound_store import make_compound_store
from ..state import GenerateSIState


def normalize_compounds_node(state: GenerateSIState) -> dict:
    compounds, order = make_compound_store(state.get("input_compounds", []))
    return {"compounds": compounds, "order": order}
