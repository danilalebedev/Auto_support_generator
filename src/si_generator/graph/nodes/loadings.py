from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState
from ...domain.reactions import calculate_reaction_loadings


def calculate_loadings_node(state: GenerateSIState) -> dict:
    generation_config = state.get("generation_config", {})
    compounds = ordered_compounds(state)
    if not generation_config.get("generate_loadings", False) and not any(compound.reaction for compound in compounds):
        return {}

    for compound in compounds:
        if compound.reaction:
            compound.reaction = calculate_reaction_loadings(compound.reaction)

    return {"compounds": state.get("compounds", {})}
