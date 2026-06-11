from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState, Issue
from ...domain.massspec import calculate_hrms


def calculate_hrms_node(state: GenerateSIState) -> dict:
    issues: list[Issue] = list(state.get("issues", []))

    for compound in ordered_compounds(state):
        if not compound.formula or not compound.hrms_found:
            continue
        try:
            result = calculate_hrms(compound.formula, compound.hrms_adduct)
        except ValueError as exc:
            issues.append(
                {
                    "code": "HRMS_CALCULATION_FAILED",
                    "severity": "warning",
                    "compound_id": compound.id,
                    "message": str(exc),
                }
            )
            continue
        compound.hrms_calculated = result.calculated_mz
        compound.hrms_ion_formula = result.ion_formula

    return {"compounds": state.get("compounds", {}), "issues": issues}
