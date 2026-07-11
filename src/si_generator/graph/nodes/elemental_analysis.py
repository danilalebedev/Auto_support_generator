from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState, Issue
from ...domain.elemental_analysis import calculate_elemental_analysis_block, found_from_block


def calculate_elemental_analysis_node(state: GenerateSIState) -> dict:
    generation_config = state.get("generation_config", {})
    if generation_config.get("include_elemental_analysis", True) is False:
        return {}
    compounds = ordered_compounds(state)
    include_all = bool(generation_config.get("calculate_elemental_analysis", False))
    if not include_all and not any(compound.elemental_analysis for compound in compounds):
        return {}

    issues: list[Issue] = list(state.get("issues", []))
    for compound in compounds:
        if compound.elemental_analysis.get("skip"):
            continue
        if not include_all and not compound.elemental_analysis:
            continue
        if not compound.formula:
            continue
        try:
            compound.elemental_analysis = calculate_elemental_analysis_block(
                compound.formula,
                found=found_from_block(compound.elemental_analysis),
            )
        except ValueError as exc:
            issues.append(
                {
                    "code": "ELEMENTAL_ANALYSIS_FAILED",
                    "severity": "warning",
                    "compound_id": compound.id,
                    "message": str(exc),
                }
            )

    return {"compounds": state.get("compounds", {}), "issues": issues}
