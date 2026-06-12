from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState
from ...domain.loadings_workflow import apply_loadings_workflow
from ...domain.reactions import calculate_reaction_loadings


def calculate_loadings_node(state: GenerateSIState) -> dict:
    generation_config = state.get("generation_config", {})
    compounds = ordered_compounds(state)
    changed = False

    if generation_config.get("generate_loadings", False):
        request = state.get("request")
        if request is not None:
            issues = apply_loadings_workflow(compounds, request.input_base_dir)
            if issues:
                state.setdefault("issues", []).extend(issues)
            changed = bool(issues) or any(compound.reaction.get("source") == "loadings_workflow" for compound in compounds)

    if not generation_config.get("generate_loadings", False) and not any(compound.reaction for compound in compounds):
        return {}

    for compound in compounds:
        if compound.reaction:
            compound.reaction = calculate_reaction_loadings(compound.reaction)
            changed = True

    result: dict = {}
    if changed:
        result["compounds"] = state.get("compounds", {})
    if state.get("issues"):
        result["issues"] = state.get("issues", [])
    return result
