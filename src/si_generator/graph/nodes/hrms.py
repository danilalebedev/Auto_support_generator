from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState, Issue
from ...domain.massspec import build_hrms_block


def calculate_hrms_node(state: GenerateSIState) -> dict:
    issues: list[Issue] = list(state.get("issues", []))

    for compound in ordered_compounds(state):
        if not compound.formula or not compound.hrms_found:
            continue
        try:
            result = build_hrms_block(
                formula=compound.formula,
                label=compound.hrms_label,
                adduct=compound.hrms_adduct,
                found_text=compound.hrms_found,
                isotope_policy=str(compound.hrms.get("isotope_policy", "auto_halogen")),
                isotope_labels=compound.hrms.get("isotope_labels"),
            )
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
        compound.hrms = result
        compound.hrms_calculated = float(result["calculated_mz"])
        compound.hrms_ion_formula = str(result["ion_formula"])

    return {"compounds": state.get("compounds", {}), "issues": issues}
